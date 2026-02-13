# works with both python 2 and 3
from __future__ import print_function

import africastalking

class SMS:
    def __init__(self):
        # Set your app credentials
        self.username = "iviotdemo"
        self.api_key = "atsk_81e4c0fb0f82545d0482c2082cd5d73981d602947078ac9d8f4f0a565ea89426b97e34ea"

        # Initialize the SDK
        africastalking.initialize(self.username, self.api_key)

        # Get the SMS service
        self.sms = africastalking.SMS

    def send_start_1_percent(self):
        # Set the numbers you want to send to in international format
        # victor saf "+254703454477",
        # D saf "+254758314508"
        recipients = ["+254100210186"]

        # Start message with 1% delivered
        message = "IV monitoring started: 1% delivered."

        try:
            response = self.sms.send(message, recipients)
            print("SUCCESS: %s" % message)
            print(response)
        except Exception as e:
            print('ERROR sending "%s": %s' % (message, str(e)))

if __name__ == '__main__':
    SMS().send_start_1_percent()
