from gpiozero.pins.lgpio import LGPIOFactory # This is the correct factory for Pi 5

from gpiozero import AngularServo, Robot
from time import sleep

# --- Hardware Setup ---
# Use the LGPIOFactory instead of PiGPIOFactory
factory = LGPIOFactory() # <--- CHANGE THIS LINE

robot = Robot(
    left=(4, 23),
    right=(17, 18),
    pin_factory=factory # Keep this line, it's correct
)

servo = AngularServo(
    12,
    min_angle=0,
    max_angle=180,
    min_pulse_width=0.5/1000,
    max_pulse_width=2.5/1000,
    pin_factory=factory # Keep this line, it's correct
)

def motor_forward():
    robot.forward(0.5)  # move at half-speed
    sleep(3)
    robot.stop()

def motor_backward():
    robot.backward(0.5)
    sleep(3)
    robot.stop()

def rotate_servo_to_180():
    """Move servo to 180 degrees."""
    servo.angle = 180
    sleep(1)

def rotate_servo_to_0():
    """Move servo to 0 degrees."""
    servo.angle = 0
    sleep(1)

def shake_servo(times=2):
    """Shake servo between 45Â° and 100Â°."""
    for _ in range(times):
        servo.angle = 45
        sleep(1)
        servo.angle = 100
        sleep(1)
    # Return to 0Â°
    servo.angle = 0
    sleep(0.5)