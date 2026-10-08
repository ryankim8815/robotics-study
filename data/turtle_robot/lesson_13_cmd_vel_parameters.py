"""거북이가 점점 큰 원을 그리게 하는 Publisher 실습입니다."""

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter


class CmdVelParameterPublisher(Node):
    """거북이 속도를 발행하는 노드입니다."""

    def __init__(self):
        super().__init__('lesson_13_cmd_vel_parameters')


        self.declare_parameter('linear_speed', 1.0)
        self.declare_parameter('angular_speed', 1.0)

        # 실습 1: /turtle1/cmd_vel에 Twist를 발행하는 Publisher를 만드세요.
        self.publisher = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)

        # 실습 2: publish_velocity를 0.1초마다 실행하는 Timer를 만드세요.
        self.timer = self.create_timer(0.1, self.publish_velocity)

    def publish_velocity(self):
        """회전 속도를 유지하고 전진 속도를 높여 원을 키웁니다."""
        # 실습 3: 현재 속도를 발행하고 다음 호출의 전진 속도를 높이세요.
        message = Twist()

        message.linear.x = self.get_parameter('linear_speed').value
        message.angular.z = self.get_parameter('angular_speed').value

        self.publisher.publish(message)



def main(args=None):
    """노드를 실행합니다."""
    rclpy.init(args=args)
    node = CmdVelParameterPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()