import gym
from gym import error, spaces, utils
from gym.utils import seeding
import numpy as np
import pybullet
from pybullet_utils import bullet_client
from hamstir_gym.utils import *

class HamstirRoomEmptyEnv(gym.Env):
    metadata = {'render.modes': ['human', 'rgb_array']}

    def __init__(self, render=True, step_ratio=120, discrete=False):
        
        self.camera_height, self.camera_width = 240, 240
        
        if discrete:
            self.action_space = spaces.Discrete(5)
            self.actions = [(0,0),(10,10),(-5,-5),(5,-5),(-5,5)]
        else:
            self.action_space = spaces.Box(-10,10,(2,),dtype=np.float32)
            self.actions = None
            
        self.observation_space = spaces.Box(low=0, high=255, shape=(self.camera_height, self.camera_width, 4), dtype=np.uint8) # returns RGBA
        
        self.physicsClientId = -1
        self.ownsPhysicsClient = False
        self.isRender = render
        self.room = None
        self.robot = None
        self.step_ratio = step_ratio # render timesteps / step(); render tstep = 1/240 sec
        self.renderer = pybullet.ER_BULLET_HARDWARE_OPENGL
        self.maxForce = 10
        
        return
    
    def _resetClient(self):
        if (self.physicsClientId>=0):
            return
            
        self.ownsPhysicsClient = True

        if self.isRender:
            self._p = bullet_client.BulletClient(connection_mode=pybullet.GUI)
        else:
            self._p = bullet_client.BulletClient()

        self.physicsClientId = self._p._client
        self._p.configureDebugVisualizer(pybullet.COV_ENABLE_GUI,0)
    
        self._p.setGravity(0,0,-10)
        
        self._p.setAdditionalSearchPath(DATA_DIR)
        
        self.room = self._p.loadURDF(DATA_DIR+"/room.urdf", useFixedBase=1)
        
        cubeStartPos = [0,2,.05]
        cubeStartOrientation = pybullet.getQuaternionFromEuler([0,0,0])
        self.robot = self._p.loadURDF(DATA_DIR+"/car.urdf", cubeStartPos, cubeStartOrientation)
        
        self.camera_link_id, left_wheel_id, right_wheel_id = find_links(self.robot)
        self.wheel_ids = [left_wheel_id, right_wheel_id]
        
        self.cameraProjection = pybullet.computeProjectionMatrixFOV(fov=90.0, aspect=1.0, nearVal=0.1, farVal=10.0)
        
    
    def reset(self):
        self._resetClient()
        
        randomizeColors(self.room)
        
        cubeStartPos = [0,2,.05]
        cubeStartOrientation = pybullet.getQuaternionFromEuler([0,0,0])
        self._p.resetBasePositionAndOrientation(self.robot, cubeStartPos, cubeStartOrientation)
        
        return self._get_img()
        
        
    def step(self, action):
        startPosition,_ = self._p.getBasePositionAndOrientation(self.robot)
        
        wheel_speeds = self.actions[action] if self.actions else action
        for wheel, vel in zip(self.wheel_ids, wheel_speeds):
            # presumably targetVelocity is in radians/second, force is in N-m -- unverified
            p.setJointMotorControl2(self.robot, wheel, pybullet.VELOCITY_CONTROL, targetVelocity=vel, force=self.maxForce)

        for _ in range(self.step_ratio):
            self._p.stepSimulation()
        
        img_arr = self._get_img()
        
        endPosition,_ = self._p.getBasePositionAndOrientation(self.robot)
        travelDistance2 = sum([(x-y)*(x-y) for x,y in zip(startPosition,endPosition)])
        
        wallDistance = getWallDistance(self.room, self.robot)
        
        done = False
        reward = 0
        if sum(wheel_speeds) > 0:
            # add travel distance only if moving forward
            reward = travelDistance2
            
        if wallDistance < 0.01:
            done=True
            reward = -100

        return img_arr, reward, done, {}
        
    def _get_img(self):
        cameraView = get_camera_view(self.robot, self.camera_link_id)
        img_params = self._p.getCameraImage(self.camera_width, self.camera_height, cameraView, self.cameraProjection, renderer=self.renderer)
        return img_params[2]

    def render(self, mode='human', close=False):

        return self._get_img()