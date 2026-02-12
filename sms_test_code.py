# works with both python 2 and 3
from __future__ import print_function

import africastalking
import time

class SMS:
    def __init__(self):
        # Set your app credentials
        self.username = "iviotdemo"
        self.api_key = "atsk_81e4c0fb0f82545d0482c2082cd5d73981d602947078ac9d8f4f0a565ea89426b97e34ea"

        # Initialize the SDK
        africastalking.initialize(self.username, self.api_key)

        # Get the SMS service
        self.sms = africastalking.SMS

    def send_message(self, message):
        """Send a single SMS message"""
        # Set the numbers you want to send to in international format
        # victor saf "+254703454477", 
        # D saf "+254758314508"
        recipients = ["+254100210186"]

        try:
            # Thats it, hit send and we'll take care of the rest.
            response = self.sms.send(message, recipients)
            print("SUCCESS: %s" % message)
            print(response)
            return True
        except Exception as e:
            print('ERROR sending "%s": %s' % (message, str(e)))
            return False

    def demonstrate_all_messages(self):
        """Demonstrate all SMS messages from the IV monitoring system"""
        print("\n" + "="*70)
        print("IV FLUID MONITORING SYSTEM - SMS DEMONSTRATION")
        print("="*70 + "\n")
        
        # Sample prescription values for demonstration
        target_volume = 1500  # mL
        duration = 120  # minutes
        
        messages = [
            ("1. START MONITORING", 
             f"IV MONITORING STARTED: {target_volume}mL OVER {duration}min (1% DELIVERED)."),
            
            ("2. MILESTONE 25%", 
             "IV DELIVERED 25%."),
            
            ("3. MILESTONE 50%", 
             "IV DELIVERED 50%."),
            
            ("4. MILESTONE 75%", 
             "IV DELIVERED 75%."),
            
            ("5. LOW VOLUME ALERT", 
             "IV LOW VOLUME (180 mL)."),
            
            ("6. BUBBLE DETECTION", 
             "BUBBLE DETECTED - CHECK IV LINE"),
            
            ("7. OCCLUSION ALERT", 
             "OCCLUSION DETECTED - CHECK IV LINE IMMEDIATELY"),
            
            ("8. NO FLOW ALERT", 
             f"NO FLOW - CHECK IV LINE (750mL DELIVERED)"),
            
            ("9. TIME ELAPSED ALERT", 
             f"TIME ELAPSED - VOLUME INCOMPLETE: 1200mL/{target_volume}mL"),
            
            ("10. COMPLETION", 
             "IV COMPLETED 100%.")
        ]
        
        print("This demonstration will send %d SMS messages showing all alert types\n" % len(messages))
        print("Press Enter to proceed or Ctrl+C to cancel...")
        try:
            input()
        except:
            pass
        
        success_count = 0
        failed_count = 0
        
        for i, (label, message) in enumerate(messages, 1):
            print("\n" + "-"*70)
            print("MESSAGE %d/%d: %s" % (i, len(messages), label))
            print("-"*70)
            
            if self.send_message(message):
                success_count += 1
            else:
                failed_count += 1
            
            # Wait 10 seconds between messages to avoid rate limiting
            if i < len(messages):
                print("\nWaiting 10 seconds before next message...")
                time.sleep(10)
        
        print("\n" + "="*70)
        print("DEMONSTRATION COMPLETE")
        print("="*70)
        print("Total Messages: %d" % len(messages))
        print("Successful: %d" % success_count)
        print("Failed: %d" % failed_count)
        print("="*70 + "\n")

if __name__ == '__main__':
    sms_demo = SMS()
    sms_demo.demonstrate_all_messages()
