import pyvisa
import math
import asyncio


ARMING_TIMEOUT = 20  # Maximum time to wait for the arming process to complete

class Keithley6220:
    def __init__(self, address):
        """
        Core functionality for the Keithley 6220.
        :param address: VISA address of the device (e.g., "GPIB0::12::INSTR").
        """
        self.address = address
        self.instrument = None
        self.start = None
        self.stop = None
        self.step = None
        self.delta = None
        self.delay = None

    def send_command_to_6220(self, command: str):
        """Send a command to the 6220 with no response expected."""
        try:
            self.instrument.write(command)
            print(f"Command sent: {command}")
        except Exception as e:
            print(f"Error sending command: {e}")

    def query_6220(self, command: str):
        """
        Send a query command to the 6220 and return the response.
        Handles empty responses, error messages, and unexpected results.
        """
        try:
            # Send the query and strip the response
            response = self.instrument.query(command).strip()

            # Check for empty response
            if not response:
                print(f"Empty response for command: {command}")
                return None

            # Check for known error message format (e.g., "-221,Settings conflict")
            if response.startswith("-") or response.startswith("+"):
                error_code, error_message = response.split(",", 1)
                error_code = int(error_code.strip())  # Convert error code to integer
                error_message = error_message.strip()
                print(f"Device returned error: {error_code}, Message: {error_message}")
                return None

            # Return valid response
            print(f"Query sent: {command}, Response: {response}")
            return response

        # except ValueError:
        #     # Handle cases where splitting the response fails
        #     print(f"Unexpected response format for command: {command}, Response: {response}")
        #     return None

        except Exception as e:
            # General exception handling for communication issues
            print(f"Error querying command '{command}': {e}")
            return None

    def send_command_to_2182(self, command: str):
        """
        Sends a command to the 2182A via the 6220 expected no response.

        :param command: The SCPI command to send to the 2182A.
        """
        try:
            full_command = f'SYST:COMM:SER:SEND "{command}"'
            self.instrument.write(full_command)
            print(f"Command sent to 2182A: {command}")
        except Exception as e:
            print(f"Error sending command to 2182A: {e}")

    def query_2182(self, command: str):
        """
        Sends a query to the 2182A via the 6220 and retrieves the response.

        :param command: The SCPI query to send to the 2182A.
        :return: The response from the 2182A.
        """
        try:
            # Send the query command to the 2182A
            send_command = f'SYST:COMM:SER:SEND "{command}"'
            self.instrument.write(send_command)

            # Retrieve the response
            response = self.instrument.query("SYST:COMM:SER:ENT?")
            print(f"Query sent to 2182A: {command}, Response: {response.strip()}")
            return response.strip()
        except Exception as e:
            print(f"Error querying 2182A: {e}")
            return None

    def connect(self):
        """
        Connect to 6220 via GPIB.
        :return: A string message indicating success or failure.
        """
        try:
            # Initialize the ResourceManager
            rm = pyvisa.ResourceManager()

            # Open the instrument connection
            self.instrument = rm.open_resource(self.address)

            # Set the termination characters (must be "\n" for GPIB)
            self.instrument.write_termination = "\n"
            self.instrument.read_termination = "\n"

            # Query and return the device ID for confirmation
            device_id = self.query_6220("*IDN?")
            return f"Connected to: {device_id}"
        except pyvisa.VisaIOError as e:
            return f"Error connecting to device: {e}"

    def disconnect(self):
        """
        Close the connection to 6220.
        """
        if self.instrument:
            self.instrument.close()
            self.instrument = None
            print("Connection closed.")

    def testing_lib_load(self):
        """
        Test function to check if the pyvisa library is loaded.
        """
        try:
            # Initialize the ResourceManager
            rm = pyvisa.ResourceManager()
            return "PYvisa library loaded successfully."
        except Exception as e:
            return f"Error loading pyvisa library: {e}"

    def check_error_message(self):
        """
        Queries the 6220 for the most recent error message.

        :return: A tuple containing the error code and message, or None if no error.
        """
        try:
            response = self.instrument.write("SYST:ERR?")
            error_code, error_message = response.split(",", 1)
            error_code = int(error_code.strip())  # Convert error code to an integer
            error_message = error_message.strip().strip('"')  # Clean up the error message

            if error_code == 0:
                print("No errors.")
                return None
            else:
                print(f"Error detected: {error_code}, Message: {error_message}")
                return error_code, error_message
        except Exception as e:
            print(f"Error querying the 6220 for errors: {e}")
            return None

    def check_2182a_presence(self):
        """
        Checks if the 2182A is detected by the 6220.

        :return: True if detected, False otherwise.
        """
        try:
            response = self.query_6220("SOUR:DELTA:NVPResent?")
            is_present = response == "1"
            print(f"2182A Presence: {'Detected' if is_present else 'Not Detected'}")
            return is_present
        except Exception as e:
            print(f"Error checking 2182A presence: {e}")
            return False

    def get_6220_id(self):
        """
        Queries the identification string of the 6220.

        :return: The identification string.
        """
        try:
            response = self.query_6220("*IDN?")
            if response:
                print(f"6220 IDN Response: {response}")
            return response
        except Exception as e:
            print(f"Error retrieving 6220 ID: {e}")
            return None

    def validate_param(self, name, value, min_val, max_val):
        if not (min_val <= value <= max_val):
            raise ValueError(f"{name} {value} is out of range ({min_val} to {max_val}).")

    def set_differential_conductance_params(self, start, stop, step, delay=0.002, delta=1e-6):
        """
        Configures the parameters for a Differential Conductance test with validation and estimates the sweep time.

        :param start: Start current in amperes (-105e-3 to 105e-3).
        :param stop: Stop current in amperes (-105e-3 to 105e-3).
        :param step: Step size in amperes (0 to 105e-3, non-zero).
        :param delay: Delay time in seconds (1e-3 to 9999.999, default = 0.002).
        :param delta: Delta current in amperes (0 to 105e-3, default = 1e-6).
        :return: Total number of data points and estimated time for the sweep (seconds), or None if validation fails.
        """
        try:
            # Validate parameters
            self.validate_param("Start value", start, min_val=-105e-3, max_val=105e-3)
            self.validate_param("Stop value", stop, min_val=-105e-3, max_val=105e-3)
            self.validate_param("Step size", step, 1e-12, 105e-3)  # Step must be > 0
            self.validate_param("Delay value", delay, 1e-3, 9999.999)
            self.validate_param("Delta value", delta, 0, 105e-3)
                # Check if stop point is greater than start point
            if stop <= start:
                raise ValueError(f"Stop value {stop} must be greater than start value {start}.")
            # Calculate the number of data points
            total_points = math.ceil(abs((stop - start) / step)) + 1
            estimated_time = total_points * delay

            # Send configuration commands to the device
            self.send_command_to_6220(f"SOUR:DCON:STAR {start}")
            self.send_command_to_6220(f"SOUR:DCON:STOP {stop}")
            self.send_command_to_6220(f"SOUR:DCON:STEP {step}") # Default or user-provided
            self.send_command_to_6220(f"SOUR:DCON:DELTA {delta}")  # Default or user-provided
            self.send_command_to_6220(f"SOUR:DCON:DELay {delay}")

            # Update instance variables
            self.start = start
            self.stop = stop
            self.step = step
            self.delta = delta
            self.delay = delay

            print(f"Parameters configured successfully.")
            print(f"Total data points: {total_points}, Estimated time: {estimated_time:.2f} seconds.")
            return total_points, estimated_time

        except ValueError as ve:
            # Catch validation errors and display the message
            print(f"Validation Error: {ve}")
            return None, None
        except Exception as e:
            # Catch any other unexpected errors
            print(f"Error setting parameters: {e}")
            return None, None

def verify_params(self):
    """
    Verifies that the parameters are correctly set on the device by querying the 6220 and comparing the values.

    :return: True if all parameters match, False otherwise.
    """
    try:
        # Query each parameter from the device
        queried_start = float(self.query_6220("SOUR:DCON:STAR?"))
        queried_stop = float(self.query_6220("SOUR:DCON:STOP?"))
        queried_step = float(self.query_6220("SOUR:DCON:STEP?"))
        queried_delta = float(self.query_6220("SOUR:DCON:DELTA?"))
        queried_delay = float(self.query_6220("SOUR:DCON:DELay?"))

        # Compare with stored values
        if (queried_start == self.start and
            queried_stop == self.stop and
            queried_step == self.step and
            queried_delta == self.delta and
            queried_delay == self.delay):
            print("All parameters are correctly set on the device.")
            return True
        else:
            print("Parameter mismatch detected. Queried values:")
            print(f"Start: {queried_start}, Expected: {self.start}")
            print(f"Stop: {queried_stop}, Expected: {self.stop}")
            print(f"Step: {queried_step}, Expected: {self.step}")
            print(f"Delta: {queried_delta}, Expected: {self.delta}")
            print(f"Delay: {queried_delay}, Expected: {self.delay}")
            return False

    except Exception as e:
        print(f"Error verifying parameters: {e}")
        return False

def check_interlock_status(self):
    """
    Checks if the interlock switch is closed.

    :return: True if interlock is closed (output enabled), False otherwise.
    """
    try:
        response = self.query_6220("OUTP:INT:TRIPped?")
        is_closed = response == "1"
        print(f"Interlock Status: {'Closed' if is_closed else 'Open'}")
        if is_closed:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error checking interlock status: {e}")
        return False

def check_arm_status(self):
    """
    Queries the arming status of the 6220 (for status check only).

    :return: True if the device is armed, False if unarmed,
             or None if an unexpected status is returned.
    """
    try:
        response = self.query_6220("SOUR:DCON:ARM?")
        if response == "1":
            print("Device is armed.")
            return True
        elif response == "0":
            print("Not armed. parameters are not set.")
            return False
        else:
            print(f"Unexpected arming status: {response}")
            return None
    except Exception as e:
        print(f"Error checking arm status: {e}")
        return None

async def monitor_arming_status(self, timeout=ARMING_TIMEOUT, interval=1):
    """
    (Do not use this for checking status. Not called directly)
    Monitors the arming status of the 6220 asynchronously .


    :param timeout: Maximum time (in seconds) to wait for the arming process to complete.
    :param interval: Time (in seconds) between each status check.
    :return: True if the device is armed successfully, False otherwise.
    """
    try:
        elapsed_time = 0
        while elapsed_time < timeout:
            status = self.query_6220("SOUR:DCON:ARM?")
            if status == "1":
                print("Device armed successfully. Ready to start the test.")
                return True
            elif status == "0":
                print("Building sweep table. Please wait...")
                await asyncio.sleep(interval)  # Non-blocking wait
                elapsed_time += interval
            else:
                print(f"Unexpected arming status: {status}")
                return False

        print("Arming process timed out.")
        return False

    except Exception as e:
        print(f"Error monitoring arming status: {e}")
        return False

async def arm_device(self):
    """
    Arms the 6220 for Differential Conductance testing asynchronously.

    Preconditions:
    - Parameters are verified and match the device's settings.
    - 2182A Nanovoltmeter is detected.
    - Interlock is closed.

    :return: True if the device is armed successfully, False otherwise.
    """
    try:
        # Step 1: Verify parameters
        if not self.verify_params():
            print("Parameter verification failed. Device not armed.")
            return False

        # Step 2: Check if 2182A is detected
        if not self.check_2182a_presence():
            print("2182A is not detected. Ensure the device is properly connected.")
            return False

        # Step 3: Ensure interlock is closed
        if not self.check_interlock_status():
            print("Interlock is not closed. Ensure the interlock switch is engaged.")
            return False

        # Step 4: Send the arm command
        self.send_command_to_6220("SOUR:DCON:ARM")
        print("Arming process initiated.")
        # todo: check if compliance is needed.
        # special step: enable compliance abort (Default is OFF, so we enable it for safety)
        self.enable_compliance_abort(self, enable=True)

        # Step 5: Monitor the arming status asynchronously
        success = await self.monitor_arming_status()
        return success

    except Exception as e:
        print(f"Error during arming process: {e}")
        return False

def set_compliance_voltage(self, value):
    """
    Sets the compliance voltage for the 6220.

    :param value: Compliance voltage in volts (0.1 to 105).
    :return: True if the compliance voltage is set successfully, False otherwise.
    """
    try:
        # Validate the compliance voltage
        if not (0.1 <= value <= 105):
            raise ValueError(f"Compliance voltage {value} is out of range (0.1 to 105 V).")

        # Send the SCPI command to set the compliance voltage
        self.send_command_to_6220(f"SOUR:COMP {value}")
        print(f"Compliance voltage set to {value} V.")

        # Verify the compliance voltage
        response = self.query_6220("SOUR:COMP?")
        if float(response) == value:
            print("Compliance voltage verified successfully.")
            return True
        else:
            print(f"Compliance voltage verification failed. Queried value: {response}")
            return False

    except ValueError as ve:
        print(f"Validation Error: {ve}")
        return False
    except Exception as e:
        print(f"Error setting compliance voltage: {e}")
        return False

def enable_compliance_abort(self, enable=True):
    """
    Enables or disables compliance abort for Differential Conductance mode.

    :param enable: True to enable compliance abort, False to disable.
    :return: True if the command succeeds, False otherwise.
    """
    try:
        # Set the compliance abort state
        state = "ON" if enable else "OFF"
        self.send_command_to_6220(f"SOUR:DCON:CAB {state}")
        print(f"Compliance abort {'enabled' if enable else 'disabled'}.")

        # Verify the state
        response = self.query_6220("SOUR:DCON:CAB?")
        if (response == "1" and enable) or (response == "0" and not enable):
            print("Compliance abort state verified successfully.")
            return True
        else:
            print(f"Compliance abort state verification failed. Queried value: {response}")
            return False

    except Exception as e:
        print(f"Error enabling compliance abort: {e}")
        return False

def query_compliance_voltage(self):
    """
    Queries the current compliance voltage value.

    :return: Compliance voltage value (in volts) if successful, None otherwise.
    """
    try:
        response = self.query_6220("SOUR:COMP?")
        compliance_voltage = float(response)
        print(f"Compliance voltage: {compliance_voltage} V")
        return compliance_voltage
    except ValueError:
        print(f"Unexpected response when querying compliance voltage: {response}")
        return None
    except Exception as e:
        print(f"Error querying compliance voltage: {e}")
        return None

