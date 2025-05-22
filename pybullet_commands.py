import pybullet as FUN
import pybullet_data
import time
import random

# FUN.connect(FUN.GUI)
FUN.setGravity(0, 0, -9.81)
FUN.setAdditionalSearchPath(pybullet_data.getDataPath())
FUN.configureDebugVisualizer(FUN.COV_ENABLE_GUI, 0)
FUN.configureDebugVisualizer(FUN.COV_ENABLE_TINY_RENDERER, 0)
FUN.configureDebugVisualizer(FUN.COV_ENABLE_RGB_BUFFER_PREVIEW, 0)
FUN.configureDebugVisualizer(FUN.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0)
FUN.configureDebugVisualizer(FUN.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)

plane_id = FUN.loadURDF("plane.urdf")

cube_start_pos = [0, 0, 1]
cube_start_orientation = FUN.getQuaternionFromEuler([0, 0, 0])
cube_id = FUN.loadURDF("cube_small.urdf", cube_start_pos, cube_start_orientation)


time_step = 1. / 240.
FUN.setTimeStep(time_step)

drop_interval = 240  
step_counter = 0





for i in range(10):
    FUN.stepSimulation()
    time.sleep(time_step)
    step_counter += 1
    time.sleep(0.1)
    # Drop the cube again every second
    if step_counter % drop_interval == 0:
        new_height = random.uniform(1.0, 2.0)
        FUN.resetBasePositionAndOrientation(cube_id, [0, 0, new_height], cube_start_orientation)
        FUN.resetBaseVelocity(cube_id, [0, 0, 0], [0, 0, 0])

    if False:
        print("nothing")

while True:
    FUN.stepSimulation()
    time.sleep(time_step)
    step_counter += 1
    time.sleep(2)
    # Drop the cube again every second
    if step_counter % drop_interval == 0:
        new_height = random.uniform(1.0, 2.0)
        FUN.resetBasePositionAndOrientation(cube_id, [0, 0, new_height], cube_start_orientation)
        FUN.resetBaseVelocity(cube_id, [0, 0, 0], [0, 0, 0])

print("Simulation finished.")


