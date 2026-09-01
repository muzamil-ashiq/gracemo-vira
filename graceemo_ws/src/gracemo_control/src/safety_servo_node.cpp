#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <memory>
#include <string>

#include "geometry_msgs/msg/twist.hpp"
#include "gracemo_interfaces/msg/body_command.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/joint_state.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "std_msgs/msg/float64.hpp"

using std::placeholders::_1;

namespace
{
constexpr double kHandDown = 0.0;
constexpr double kHandHi = 0.70;
constexpr double kHandUp = 1.5708;
constexpr double kStopRange = 1.0;
}

class SafetyServoNode : public rclcpp::Node
{
public:
  SafetyServoNode()
  : Node("safety_servo_node")
  {
    neck_yaw_ = 0.0;
    neck_pitch_ = 0.0;
    left_hand_ = kHandDown;
    right_hand_ = kHandDown;
    user_estop_ = false;
    min_range_ = 12.0;

    cmd_pub_ = create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 10);
    joint_pub_ = create_publisher<sensor_msgs::msg::JointState>("/joint_states", 10);
    neck_yaw_pub_ = create_publisher<std_msgs::msg::Float64>("/neck_yaw/cmd_pos", 10);
    neck_pitch_pub_ = create_publisher<std_msgs::msg::Float64>("/neck_pitch/cmd_pos", 10);
    left_hand_pub_ = create_publisher<std_msgs::msg::Float64>("/left_hand/cmd_pos", 10);
    right_hand_pub_ = create_publisher<std_msgs::msg::Float64>("/right_hand/cmd_pos", 10);

    scan_sub_ = create_subscription<sensor_msgs::msg::LaserScan>(
      "/scan", 10, std::bind(&SafetyServoNode::onScan, this, _1));
    desired_sub_ = create_subscription<geometry_msgs::msg::Twist>(
      "/gracemo/cmd_vel_desired", 10, std::bind(&SafetyServoNode::onDesired, this, _1));
    body_sub_ = create_subscription<gracemo_interfaces::msg::BodyCommand>(
      "/gracemo/body_command", 10, std::bind(&SafetyServoNode::onBody, this, _1));

    timer_ = create_wall_timer(
      std::chrono::milliseconds(20),
      std::bind(&SafetyServoNode::tick, this));

    RCLCPP_INFO(get_logger(), "C++ control online: servo poses + cmd_vel safety mux");
  }

private:
  void onScan(const sensor_msgs::msg::LaserScan::SharedPtr msg)
  {
    double mn = std::numeric_limits<double>::infinity();
    for (float r : msg->ranges) {
      if (std::isfinite(r) && r < mn) {
        mn = r;
      }
    }
    min_range_ = std::isfinite(mn) ? mn : 12.0;
  }

  void onDesired(const geometry_msgs::msg::Twist::SharedPtr msg)
  {
    desired_ = *msg;
  }

  void onBody(const gracemo_interfaces::msg::BodyCommand::SharedPtr msg)
  {
    const std::string & a = msg->action;
    if (a == "stop") {
      user_estop_ = true;
      desired_ = geometry_msgs::msg::Twist();
    } else if (a == "look_home") {
      neck_yaw_ = 0.0;
      neck_pitch_ = 0.0;
    } else if (a == "look_at") {
      neck_yaw_ = std::clamp(static_cast<double>(msg->x), -1.2, 1.2);
      neck_pitch_ = std::clamp(static_cast<double>(msg->y != 0.0f ? msg->y : 0.15), -0.5, 0.6);
    } else if (a == "hand_hi") {
      left_hand_ = right_hand_ = kHandHi;
    } else if (a == "hand_up") {
      left_hand_ = right_hand_ = kHandUp;  // 90 degrees (1.5708 rad)
    } else if (a == "hand_down") {
      left_hand_ = right_hand_ = kHandDown;
    } else if (a == "navigate_to") {
      user_estop_ = false;
    }
  }

  void tick()
  {
    const bool blocked = user_estop_ || min_range_ < kStopRange;
    geometry_msgs::msg::Twist out;
    if (!blocked) {
      out = desired_;
    }
    cmd_pub_->publish(out);

    sensor_msgs::msg::JointState js;
    js.header.stamp = now();
    js.name = {"neck_yaw", "neck_pitch", "left_hand", "right_hand"};
    js.position = {neck_yaw_, neck_pitch_, left_hand_, right_hand_};
    joint_pub_->publish(js);

    auto pub_pos = [](const rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr & pub, double v) {
      std_msgs::msg::Float64 m;
      m.data = v;
      pub->publish(m);
    };
    pub_pos(neck_yaw_pub_, neck_yaw_);
    pub_pos(neck_pitch_pub_, neck_pitch_);
    pub_pos(left_hand_pub_, left_hand_);
    pub_pos(right_hand_pub_, right_hand_);
  }

  double neck_yaw_;
  double neck_pitch_;
  double left_hand_;
  double right_hand_;
  double min_range_;
  bool user_estop_;
  geometry_msgs::msg::Twist desired_;

  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_pub_;
  rclcpp::Publisher<sensor_msgs::msg::JointState>::SharedPtr joint_pub_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr neck_yaw_pub_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr neck_pitch_pub_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr left_hand_pub_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr right_hand_pub_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr desired_sub_;
  rclcpp::Subscription<gracemo_interfaces::msg::BodyCommand>::SharedPtr body_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<SafetyServoNode>());
  rclcpp::shutdown();
  return 0;
}
