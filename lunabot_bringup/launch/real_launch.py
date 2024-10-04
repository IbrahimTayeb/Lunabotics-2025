import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command
from launch.conditions import LaunchConfigurationEquals
from launch.actions import (
    IncludeLaunchDescription,
    DeclareLaunchArgument,
    TimerAction,
    GroupAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import (
    get_package_share_directory,
    get_package_share_path,
)


def generate_launch_description():
    simulation_dir = get_package_share_path("lunabot_simulation")
    config_dir = get_package_share_directory("lunabot_config")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")
    realsense_dir = get_package_share_path("realsense2_camera")

    urdf_file = os.path.join(simulation_dir, "urdf", "bulldozer_bot.xacro")
    nav2_params_file = os.path.join(config_dir, "params", "nav2_real_params.yaml")
    ekf_params_file = os.path.join(config_dir, "params", "ekf_params.yaml")
    rtabmap_params_file = os.path.join(config_dir, "params", "rtabmap_params.yaml")
    s2l_filter_params_file = os.path.join(
        config_dir, "params", "s2l_filter_params.yaml"
    )

    declare_robot_mode = DeclareLaunchArgument(
        "robot_mode", default_value="manual", choices=["manual", "autonomous"]
    )

    robot_description = Command(["xacro ", urdf_file])

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description, "use_sim_time": False}],
    )

    joint_state_publisher_node = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        parameters=[{"use_sim_time": False}],
    )

    map_to_odom_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=["0", "0", "0", "0", "0", "0", "map", "odom"],
        output="screen",
        name="static_transform_publisher",
    )

    rgbd_sync1_node = Node(
        package="rtabmap_sync",
        executable="rgbd_sync",
        name="rgbd_sync1",
        output="screen",
        parameters=[{"approx_sync": True, "sync_queue_size": 1000}],
        remappings=[
            ("rgb/image", "/d456/color/image_raw"),
            ("depth/image", "/d456/depth/image_rect_raw"),
            ("rgb/camera_info", "/d456/color/camera_info"),
            ("rgbd_image", "rgbd_image"),
        ],
        namespace="d456",
        arguments=["--ros-args", "--log-level", "error"],
    )

    rgbd_sync2_node = Node(
        package="rtabmap_sync",
        executable="rgbd_sync",
        name="rgbd_sync2",
        output="screen",
        parameters=[{"approx_sync": True, "sync_queue_size": 1000}],
        remappings=[
            ("rgb/image", "/d455/color/image_raw"),
            ("depth/image", "/d455/depth/image_rect_raw"),
            ("rgb/camera_info", "/d455/color/camera_info"),
            ("rgbd_image", "rgbd_image"),
        ],
        namespace="d455",
        arguments=["--ros-args", "--log-level", "error"],
    )

    slam_node = Node(
        package="rtabmap_slam",
        executable="rtabmap",
        name="rtabmap",
        output="screen",
        parameters=[
            rtabmap_params_file,
            {
                "rgbd_cameras": 2,
                "subscribe_depth": False,
                "subscribe_rgbd": True,
                "subscribe_rgb": False,
                "subscribe_odom_info": True,
                "frame_id": "base_link",
                "map_frame_id": "map",
                "odom_frame_id": "odom",
                "publish_tf": False,
                "database_path": "",
                "approx_sync": True,
                "sync_queue_size": 1000,
                "subscribe_scan_cloud": False,
                "subscribe_scan": True,
            },
        ],
        remappings=[
            ("rgbd_image0", "/d456/rgbd_image"),
            ("rgbd_image1", "/d455/rgbd_image"),
            ("scan", "/scan"),
        ],
        arguments=[
            "--ros-args",
            "--log-level",
            "error",
        ],
    )

    icp_odometry_node = Node(
        package="rtabmap_odom",
        executable="icp_odometry",
        output="screen",
        parameters=[
            {
                "frame_id": "base_link",
                "odom_frame_id": "odom",
                "publish_tf": False,
                "approx_sync": True,
                "Reg/Strategy": "1",
                "ICP/MaxCorrespondenceDistance": "0.5",
                "ICP/MaxIterations": "1.0",
                "ICP/Epsilon": "0.00001",
            }
        ],
        remappings=[
            ("scan", "/scan"),
            ("odom", "/icp_odom"),
        ],
        arguments=["--ros-args", "--log-level", "error"],
    )

    rf2o_odometry_node = Node(
        package="rf2o_laser_odometry",
        executable="rf2o_laser_odometry_node",
        name="rf2o_laser_odometry",
        output="screen",
        parameters=[
            {
                "laser_scan_topic": "/scan",
                "odom_topic": "/rf2o_odom",
                "publish_tf": False,
                "base_frame_id": "base_link",
                "odom_frame_id": "odom",
                "init_pose_from_topic": "",
                "freq": 50.0,
            }
        ],
        arguments=["--ros-args", "--log-level", "error"],
    )

    ekf_node = Node(
        package="robot_localization",
        executable="ekf_node",
        name="ekf_filter_node",
        output="screen",
        parameters=[ekf_params_file],
        remappings=[
            ("/odometry/filtered", "/odom"),
        ],
    )

    localization_server_node = Node(
        package="lunabot_system",
        executable="localization_server",
        name="localization_server",
        output="screen",
    )

    navigation_client_node = Node(
        package="lunabot_system",
        executable="navigation_client",
        name="navigation_client",
        output="screen",
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, "launch", "navigation_launch.py")
        ),
        launch_arguments={
            "use_sim_time": False,
            "params_file": nav2_params_file,
        }.items(),
    )

    s3_lidar_node = Node(
        package="rplidar_ros",
        executable="rplidar_node",
        name="rplidar_node",
        parameters=[
            {
                "channel_type": "serial",
                "serial_port": "/dev/ttyUSB0",
                "serial_baudrate": 1000000,
                "frame_id": "lidar1_link",
                "inverted": False,
                "angle_compensate": True,
                "scan_mode": "DenseBoost",
            }
        ],
        output="screen",
    )

    s2l_lidar_node = Node(
        package="rplidar_ros",
        executable="rplidar_node",
        name="rplidar_node",
        parameters=[
            {
                "channel_type": "serial",
                "serial_port": "/dev/ttyUSB1",
                "serial_baudrate": 1000000,
                "frame_id": "lidar2_link",
                "inverted": False,
                "angle_compensate": True,
                "scan_mode": "DenseBoost",
            }
        ],
        output="screen",
        remappings=[("/scan", "/scan_raw")],
    )

    s2l_filter_node = Node(
        package="laser_filters",
        executable="scan_to_scan_filter_chain",
        parameters=[s2l_filter_params_file],
        remappings=[("/scan", "/scan_raw"), ("/scan_filtered", "/scan")],
    )

    dual_camera_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                realsense_dir,
                "launch",
                "rs_multi_camera_launch.py",
            )
        ),
        launch_arguments={
            "camera_name1": "d455",
            "camera_namespace1": "d455",
            "device_type1": "d455",
            "enable_gyro1": "true",
            "enable_accel1": "true",
            "unite_imu_method1": "2",
            "depth_module.profile1": "640x360x60",
            "rgb_camera.profile1": "640x360x60",
            "camera_name2": "d456",
            "camera_namespace2": "d456",
            "device_type2": "d456",
            "enable_gyro2": "true",
            "enable_accel2": "true",
            "unite_imu_method2": "2",
            "depth_module.profile2": "640x360x60",
            "rgb_camera.profile2": "640x360x60",
        }.items(),
    )

    d455_imu_filter = Node(
        package="imu_complementary_filter",
        executable="complementary_filter_node",
        name="complementary_filter_gain_node",
        output="screen",
        parameters=[
            {"publish_tf": False},
            {"fixed_frame": "odom"},
            {"do_bias_estimation": True},
            {"do_adaptive_gain": True},
            {"use_mag": False},
            {"gain_acc": 0.01},
            {"gain_mag": 0.01},
        ],
        remappings=[
            ("/imu/data_raw", "/imu/d455/data_raw"),
            ("/imu/data", "/imu/d455/data"),
        ],
    )

    d456_imu_filter = Node(
        package="imu_complementary_filter",
        executable="complementary_filter_node",
        name="complementary_filter_gain_node",
        output="screen",
        parameters=[
            {"publish_tf": False},
            {"fixed_frame": "odom"},
            {"do_bias_estimation": True},
            {"do_adaptive_gain": True},
            {"use_mag": False},
            {"gain_acc": 0.01},
            {"gain_mag": 0.01},
        ],
        remappings=[
            ("/imu/data_raw", "/imu/d456/data_raw"),
            ("/imu/data", "/imu/d456/data"),
        ],
    )

    imu_rotator_node = Node(package="lunabot_system", executable="imu_rotator")

    joy_node = Node(
        package="joy",
        executable="joy_node",
        name="joy_node",
    )

    robot_controller_node = Node(
        package="lunabot_system",
        executable="robot_controller",
        parameters=[
            {
                "xbox_mode": True,
                "outdoor_mode": False,
            }
        ],
    )

    manual_sequence = GroupAction(
        actions=[
            TimerAction(
                period=2.0,
                actions=[
                    icp_odometry_node,
                    rf2o_odometry_node,
                    ekf_node,
                ],
            ),
            TimerAction(
                period=8.0,
                actions=[
                    slam_node,
                ],
            ),
            TimerAction(
                period=15.0,
                actions=[
                    nav2_launch,
                ],
            ),
        ],
    )

    autonomous_sequence = GroupAction(
        actions=[
            TimerAction(
                period=5.0,
                actions=[
                    localization_server_node,
                    navigation_client_node,
                ],
            ),
            TimerAction(
                period=50.0,
                actions=[
                    icp_odometry_node,
                    rf2o_odometry_node,
                    ekf_node,
                    slam_node,
                ],
            ),
            TimerAction(
                period=60.0,
                actions=[
                    nav2_launch,
                ],
            ),
        ],
    )

    ld = LaunchDescription()

    ld.add_action(declare_robot_mode)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(rgbd_sync1_node)
    ld.add_action(rgbd_sync2_node)
    ld.add_action(map_to_odom_tf)
    ld.add_action(s3_lidar_node)
    ld.add_action(s2l_lidar_node)
    ld.add_action(s2l_filter_node)
    ld.add_action(dual_camera_launch)
    ld.add_action(d455_imu_filter)
    ld.add_action(d456_imu_filter)
    ld.add_action(imu_rotator_node)
    ld.add_action(joy_node)
    ld.add_action(robot_controller_node)

    if LaunchConfigurationEquals("control_method", "manual"):
        ld.add_action(manual_sequence)

    else:
        ld.add_action(autonomous_sequence)

    return ld