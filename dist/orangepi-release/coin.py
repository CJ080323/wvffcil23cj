import time

try:
    import OPi.GPIO as GPIO
except ImportError:
    GPIO = None


COIN_PIN = 7

if GPIO is not None:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(COIN_PIN, GPIO.IN)


def gpio_available():
    return GPIO is not None


def wait_coin(poll_interval=0.1, debounce_seconds=1):
    if GPIO is None:
        raise RuntimeError("OPi.GPIO is not available on this machine.")

    while True:
        if GPIO.input(COIN_PIN) == 1:
            time.sleep(debounce_seconds)
            return True
        time.sleep(poll_interval)
