# -----------------------------------------------------------------------------
# Copyright 2024 Bernd Pfrommer <bernd.pfrommer@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#


#
# Example file for two Blackfly S cameras that are *externally triggered*, i.e
# you must provide an external hardware synchronization pulse to both cameras!
#
# One of them creates a master controller, the other one a follower. The exposure
# parameters are determined by the master. This is a useful setup for e.g. a
# synchronized stereo camera.
#

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument as LaunchArg
from launch.actions import OpaqueFunction
from launch.substitutions import LaunchConfiguration as LaunchConfig
from launch.substitutions import PathJoinSubstitution as PJoin
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.substitutions import FindPackageShare

camera_list = {
    'cam0': '21039765',
    'cam1': '21081518',
}

exposure_controller_parameters = {
    'brightness_target': 120,  # from 0..255
    'brightness_tolerance': 10,  # when to update exposure/gain
    # watch that max_exposure_time is short enough
    # to support the trigger frame rate!
    # 'max_exposure_time': 15000,  # usec
    # 'min_exposure_time': 5000,  # usec
    'max_exposure_time': 100000,  # usec 
    'min_exposure_time': 1000,  # usec
    'max_gain': 0.0,
    'gain_priority': False,
}

cam_parameters = {

    # ROS camera parameters
    'debug': False,
    'quiet': True,
    'compute_brightness': True, # Assumed to be true
    'adjust_timestamp': True,
    'acquisition_timeout': 1000.0,
    'buffer_queue_size': 1,

    # Parameters for the FLIR Firefly camera
    'acquisition_mode': 'SingleFrame',
    'exposure_mode': 'Timed',
    'exposure_auto': 'Off',
    'exposure_time': 10000.0, # Not used if exposure_auto is on
    # 'acquisition_frame_rate': 10.0, # Not used if single frame mode is on
    'acquisition_frame_rate_enable': True,
    'trigger_mode': 'Off', # Have to set to 'Off' to configure trigger
    'trigger_selector': 'FrameStart',
    'trigger_source': 'Line3',
    'trigger_activation': 'FallingEdge',
    'line_selector': 'Line3',
    'line_mode': 'Input',
    'trigger_mode': 'On',
    'sensor_shutter_mode': 'Global',

    'gain_auto': 'Off',
    'black_level_selector': 'All',
    'black_level': 0.0,
    'black_level_clamping_enable': False,

    'gamma': 1.0,
    'gamma_enable': True,
    
    'width': 1440,
    'height': 1080,
    'pixel_format': 'Mono8',

    # Must enable chunk mode and chunks: frame id, exposure time, and gain
    'chunk_mode_active': True,
    'chunk_selector_frame_id': 'FrameID',
    'chunk_enable_frame_id': True,
    'chunk_selector_exposure_time': 'ExposureTime',
    'chunk_enable_exposure_time': True,
    'chunk_selector_gain': 'Gain',
    'chunk_enable_gain': True,

    # Timestamp is optional, but useful for debugging
    'chunk_selector_timestamp': 'Timestamp',
    'chunk_enable_timestamp': True,
}


def make_parameters(context):
    """Launch synchronized camera driver node."""
    pd = LaunchConfig('camera_parameter_directory')
    calib_url = 'file://' + LaunchConfig('calibration_directory').perform(context) + '/'

    exp_ctrl_names = [cam + '.exposure_controller' for cam in camera_list.keys()]
    driver_parameters = {
        'cameras': list(camera_list.keys()),
        'exposure_controllers': exp_ctrl_names,
        'ffmpeg_image_transport.encoding': 'hevc_nvenc',  # only for ffmpeg image transport
    }
    # generate identical exposure controller parameters for all cameras
    for exp in exp_ctrl_names:
        driver_parameters.update(
            {exp + '.' + k: v for k, v in exposure_controller_parameters.items()}
        )
    # now set cam0 to be master, cam1 to be follower
    driver_parameters[exp_ctrl_names[0] + '.type'] = 'master'
    driver_parameters[exp_ctrl_names[1] + '.type'] = 'follower'
    # tell camera 1 that the master is (camera 0)
    driver_parameters[exp_ctrl_names[1] + '.master'] = exp_ctrl_names[0]

    # generate camera parameters
    cam_parameters['parameter_file'] = PJoin([pd, 'firefly.yaml'])
    for cam, serial in camera_list.items():
        cam_params = {cam + '.' + k: v for k, v in cam_parameters.items()}
        cam_params[cam + '.serial_number'] = serial
        cam_params[cam + '.camerainfo_url'] = calib_url + serial + '.yaml'
        cam_params[cam + '.frame_id'] = cam
        driver_parameters.update(cam_params)  # insert into main parameter list
        # link the camera to its exposure controller. Each camera has its own controller
        driver_parameters.update({cam + '.exposure_controller_name': cam + '.exposure_controller'})
    return driver_parameters


def launch_setup(context, *args, **kwargs):
    container = ComposableNodeContainer(
        name='cam_sync_container',
        namespace='',
        package='rclcpp_components',
        executable='component_container',
        composable_node_descriptions=[
            ComposableNode(
                package='spinnaker_synchronized_camera_driver',
                plugin='spinnaker_synchronized_camera_driver::SynchronizedCameraDriver',
                name='cam_sync',
                parameters=[make_parameters(context)],
                extra_arguments=[{'use_intra_process_comms': True}],
            ),
        ],
        output='screen',
    )  # end of container
    return [container]


def generate_launch_description():
    return LaunchDescription(
        [
            LaunchArg(
                'camera_parameter_directory',
                default_value=PJoin([FindPackageShare('spinnaker_camera_driver'), 'config']),
                description='root directory for camera parameter definitions',
            ),
            LaunchArg(
                'calibration_directory',
                default_value=['camera_calibrations'],
                description='root directory for camera calibration files',
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
