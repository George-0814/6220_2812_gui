from http.client import responses
import re
import pyvisa
import math
import asyncio
import time
import numpy as np
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
        self.is_armed = False
        self.under_arming = False
        self.compliance_voltage = None
        self.compliance_abort = None
        self.output_state = None  # Stores ON/OFF state of the output
        self.inner_shield_status = None  # Stores inner shield state (GUARD or OLOW)
        self.total_points = None
        self.estimated_time = None
        self.output_low_status = None  # Stores the output low status (FLOATING or GROUNDED)

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
        :return: The response from the 6220, or None if an error occurs.
        """
        try:
            # Send the query and strip the response
            response = self.instrument.query(command).strip()

            # Check for empty response
            if not response:
                print(f"Empty response for command: {command}")
                return None

            # # Check for known error message format (e.g., "-221,Settings conflict")
            # if response.startswith("-") or response.startswith("+"):
            #     error_code, error_message = response.split(",", 1)
            #     error_code = int(error_code.strip())  # Convert error code to integer
            #     error_message = error_message.strip()
            #     print(f"Device returned error: {error_code}, Message: {error_message}")
            #     print(f"ERROR, Query sent: {command}, Response: {response}")
            #     return None

            # Check for known SCPI error message format (e.g., "-221,Settings conflict")
            # SCPI errors are typically in the format "-221, message"
            if "," in response and (response.startswith("-") or response.startswith("+")):
                try:
                    error_code, error_message = response.split(",", 1)
                    error_code = int(error_code.strip())  # Convert error code to integer
                    error_message = error_message.strip()
                    print(f"Device returned error: {error_code}, Message: {error_message}")
                    return None
                except ValueError:
                    print(f"Unexpected response format: {response}")  # Safety check
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
        # todo: some issue with the query command
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

            response = self.instrument.query("SYST:COMM:SER:ENT?").strip()
            print(f"Query sent to 2182A: {command}, Response: {response}")
            buf_clear = self.instrument.read()  # Clear the buffer
            return response
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

            return "library loaded successfully."
        except Exception as e:
            return f"Error loading pyvisa library: {e}"

    def check_error_message(self):
        """
        Queries the 6220 for the most recent error message.

        :return: A tuple containing the error code and message, or None if no error.
        """
        try:
            response = self.query_6220("SYST:ERR?")
            print(response)
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
            return f"Exception: {e}"

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
        """
        NOT called directly. Validates a parameter value against a specified range.
        """
        if not (min_val <= value <= max_val):
            raise ValueError(f"{name} {value} is out of range ({min_val} to {max_val}).")

    def set_differential_conductance_params(self, start, stop, step, delay=0.002, delta=1e-5):
        """
        Configures the parameters and buffer size for a Differential Conductance test with validation and estimates the sweep time.

        :param start: Start current in amperes (-105e-3 to 105e-3).
        :param stop: Stop current in amperes (-105e-3 to 105e-3).
        :param step: Step size in amperes (0 to 105e-3, non-zero).
        :param delay: Delay time in seconds (1e-3 to 9999.999, default = 0.002).
        :param delta: Delta current in amperes (0 to 105e-3, default = 1e-6).
        # todo : check the delta value minimum (is allowd to 1e-5 not 1e-6)
        :return: tuple (total_points, estimated_time) for the sweep, or (None, message) if validation fails.
        """
        try:
            # Validate parameters
            self.validate_param("Start value", start, min_val=-105e-3, max_val=105e-3)
            self.validate_param("Stop value", stop, min_val=-105e-3, max_val=105e-3)
            self.validate_param("Step size", step, 1e-12, 105e-3)  # Step must be > 0
            self.validate_param("Delay value", delay, 1e-3, 9999.999)
            # todo: check the minimal delta value
            self.validate_param("Delta value", delta, 1e-5, 105e-3)
                # Check if stop point is greater than start point
            if stop <= start:
                raise ValueError(f"Stop value {stop} must be greater than start value {start}.")
            # Calculate the number of data points
            self.total_points = math.ceil(round((abs(stop-start)/step),6)) + 1
            if self.total_points > 65530:
                raise ValueError(f"Calculated buffer size {self.total_points} exceeds maximum limit of 65530 readings.")
            # set the buffer size
            self.set_buffer_size()
            # Calculate the estimated time for the sweep
            print(f"numerical: {round((abs(stop-start)/step),9)}")
            self.estimated_time = self.total_points * delay

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
            print(f"Total data points: {self.total_points}, Estimated time: {self.estimated_time:.3f} seconds.")
            return str(self.total_points), f"{self.estimated_time:.3f}"

        except ValueError as ve:
            # Catch validation errors and display the message
            print(f"Validation Error: {ve}")
            return None, f"Validation Error: {ve}"
        except Exception as e:
            # Catch any other unexpected errors
            print(f"Error setting parameters: {e}")
            return None, f"Error setting parameters: {e}"

    def verify_params(self):
        """
        Not called directly
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

        :return: True if interlock is closed (output enabled), False otherwise. None for error.
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
            return None

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
            # else:
            #     print(f"Unexpected arming status: {response}")
            #     return None
        except Exception as e:
            print(f"Error checking arm status: {e}")
            return None

    # async def monitor_arming_status(self, timeout=ARMING_TIMEOUT, interval=1):
    #     """
    #     (BUG NOT FIXED)
    #     (Do not use this for checking status. Not called directly)
    #     Monitors the arming status of the 6220 asynchronously .
    #
    #
    #     :param timeout: Maximum time (in seconds) to wait for the arming process to complete.
    #     :param interval: Time (in seconds) between each status check.
    #     :return: True if the device is armed successfully, False otherwise.
    #     """
    #     try:
    #         elapsed_time = 0
    #         while elapsed_time < timeout:
    #             status = self.query_6220("SOUR:DCON:ARM?")
    #             if status == "1":
    #                 print("Device armed successfully. Ready to start the test.")
    #                 self.is_armed = True
    #                 self.under_arming = False
    #                 return True
    #             elif status == "0":
    #                 print("Building sweep table. Please wait...")
    #                 await asyncio.sleep(interval)  # Non-blocking wait
    #                 elapsed_time += interval
    #             else:
    #                 print(f"Unexpected arming status: {status}")
    #                 self.is_armed = False
    #                 self.under_arming = False
    #                 return False
    #
    #         print("Arming process timed out.")
    #         # todo: abort the process if needed
    #         return False
    #
    #     except Exception as e:
    #         print(f"Error monitoring arming status: {e}")
    #         return False

    def arm_device(self):
        """
        Arms the 6220 for Differential Conductance testing asynchronously.

        Preconditions:
        - Parameters are verified and match the device's settings.
        - 2182A Nanovoltmeter is detected.
        - Interlock is closed.
        Steps:
        - Verify params
        - Check 2182A
        - Check interlock
        - Send arm command

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
            return True

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
            self.send_command_to_6220(f"SOUR:CURR:COMP {value}")
            print(f"Compliance voltage set to {value} V.")

            # Verify the compliance voltage
            response = self.query_6220("SOUR:CURR:COMP?")
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
            # response = self.query_6220("SOUR:DCON:CAB?")
            # if (response == "1" and enable) or (response == "0" and not enable):
            #     print(f"Compliance abort state verified successfully. The device is set to"
            #           f" {"enabled" if response == "1" else "disabled"}.")
            #     return True
            # else:
            #     print(f"Compliance abort state verification failed. Queried value: {response}")
            #     return False
            query_comp_enable_state = self.query_compliance_abort()
            if query_comp_enable_state:
                print(f"Compliance abort state verified successfully. The device is set to"
                      f" {'enabled' if query_comp_enable_state else 'disabled'}.")
                return True
            elif query_comp_enable_state is False:
                print(f"Compliance abort state verified successfully. The device is set to"
                      f" {'enabled' if query_comp_enable_state else 'disabled'}.")
                return False
            else:
                print(f"Compliance abort state verification failed. Queried value: {query_comp_enable_state}")
                return False

        except Exception as e:
            print(f"Error enabling compliance abort: {e}")
            return False

    def query_compliance_abort(self):
        """
        Queries the current compliance abort status.

        :return: True if compliance abort is enabled, False if disabled, None otherwise.
        """
        try:
            response = self.query_6220("SOUR:DCON:CAB?")
            if response == "1":
                print("Compliance abort is enabled.")
                self.compliance_abort = True
                return True
            elif response == "0":
                print("Compliance abort is disabled.")
                self.compliance_abort = False
                return False
            else:
                print(f"Unexpected response when querying compliance abort: {response}")
                return None
        except Exception as e:
            print(f"Error querying compliance abort: {e}")
            return None

    def query_compliance_voltage(self):
        """
        Queries the current compliance voltage value.

        :return: Compliance voltage value (in volts) if successful, None otherwise.
        """
        try:
            response = self.query_6220("SOUR:CURR:COMP?")
            compliance_voltage = float(response)
            print(f"Compliance voltage: {compliance_voltage} V")
            self.compliance_voltage = compliance_voltage
            return compliance_voltage
        except ValueError:
            print(f"Unexpected response when querying compliance voltage: {response}")
            return None
        except Exception as e:
            print(f"Error querying compliance voltage: {e}")
            return None

    def abort_process(self):
        """
        Aborts the armed or running process on the 6220.
        Not intended for use during the arming process.

        :return: True if the abort command succeeds, False otherwise.
        """

        try:
            # Send the abort command
            self.send_command_to_6220("SOUR:SWE:ABOR")
            print("Process aborted successfully.")
            return True
        except Exception as e:
            print(f"Error aborting process: {e}")
            return False

    def query_inner_shield(self):
        """
        NOT called directly.
        Queries the current setting of the inner shield on the 6220.
        :return: The current inner shield setting (GUARD/OLOW) or None if an error occurs.
        """
        try:
            response = self.query_6220("OUTP:ISHield?")
            print(f"Current Inner Shield Setting: {response}")
            return response.strip().upper()
        except Exception as e:
            print(f"Error querying inner shield setting: {e}")
            return None

    def is_output_off(self):
        """
        NOT called directly.
        Checks if the output is OFF before modifying any configuration.
        :return: True if OFF, False if ON.
        """
        try:
            response = self.query_6220("OUTP:STATe?").strip()
            if response == "0":
                print("Output is OFF. Safe to modify Inner Shield.")
                return True
            else:
                print("Output is ON. Inner Shield modification is not allowed.")
                return False
        except Exception as e:
            print(f"Error querying output state: {e}")
            return None

    def set_inner_shield_to_guard(self):
        """
        Modifies the inner shield to GUARD setting only if the output is OFF.
        :return: no value
        """
        try:
            if not self.is_output_off():
                print("Skipping Inner Shield modification: Output is ON.")
                return "OUTPUT_ON"

            # Set Inner Shield to Guard
            self.send_command_to_6220("OUTP:ISHield GUARd")

            # Verify setting
            response = self.query_inner_shield()
            if response == "GUARD" or response == "GUAR":
                print("Inner shield successfully set to Guard.")
                return True
            else:
                print(f"Warning: Inner shield setting not confirmed, received: {response}")
                return False
        except Exception as e:
            print(f"Error setting inner shield to Guard: {e}")
            return None

    def update_output_state(self):
        """
        Queries and updates the stored output state.
        :return: The current output state (ON/OFF) or None if exception happens.
        """
        try:
            response = self.query_6220("OUTP:STATe?").strip()
            self.output_state = "ON" if response == "1" else "OFF"
            print(f"Output State Updated: {self.output_state}")
            return self.output_state
        except Exception as e:
            print(f"Error querying output state: {e}")
            return None

    def update_inner_shield_status(self):
        """
        Queries and updates the stored inner shield status.
        :return: The current inner shield status (GUARD/OLOW) or None if exception happens.
        """
        try:
            response = self.query_6220("OUTP:ISHield?").strip().upper()
            self.inner_shield_status = response
            print(f"Inner Shield Status Updated: {self.inner_shield_status}")
            return self.inner_shield_status
        except Exception as e:
            print(f"Error querying inner shield setting: {e}")
            return None

    def turn_output_on(self):
        """
        NOT use in differential conductance mode.
        Turns ON the output of the 6220 and updates stored output state.
        :return: no value
        """
        try:
            if self.output_state == "ON":
                print("Output is already ON. No action taken.")
                return

            self.send_command_to_6220("OUTP ON")
            self.update_output_state()

            if self.output_state == "ON":
                print("Output successfully turned ON.")
            else:
                print("Warning: Output state not confirmed.")
        except Exception as e:
            print(f"Error turning output ON: {e}")

    def turn_output_off(self):
        """
        Turns OFF the output of the 6220 and updates the stored output state.
        :return: no value
        """
        try:
            if self.output_state == "OFF":
                print("Output is already OFF. No action taken.")
                return

            self.send_command_to_6220("OUTP OFF")
            self.update_output_state()  # Update stored state after command

            if self.output_state == "OFF":
                print("Output successfully turned OFF.")
            else:
                print("Warning: Output state not confirmed.")
        except Exception as e:
            print(f"Error turning output OFF: {e}")

    def query_measurement_unit(self):
        """
        Queries the current measurement unit setting on the Keithley 6220.

        :return: The current unit as a string ("V", "Ω", "S", or "W"), or None if an error occurs.
        """
        try:
            response = self.query_6220("UNIT?")
            if response is None:
                print("Error: Failed to query measurement unit.")
                return None

            response = response.strip().upper()
            if response in ["V", "O", "S", "W"]:
                print(f"Current Measurement Unit: {response}")
                return response
            else:
                print(f"Unexpected response when querying measurement unit: '{response}'")
                return None
        except Exception as e:
            print(f"Error querying measurement unit: {e}")
            return None

    def set_measurement_unit(self, unit: str):
        """
        Sets the measurement unit for Differential Conductance mode.
        :param unit: "V" (Volts), "S" (Siemens), "O" (Ohms), "W" (Watts).
        """
        # todo: check the unit value "O"
        try:
            unit = unit.upper()
            valid_units = {"V", "S", "O", "W"}
            if unit not in valid_units:
                print(f"Invalid unit '{unit}'. Choose from {valid_units}.")
                return

            self.send_command_to_6220(f"UNIT {unit}")
            print(f"Measurement unit set to {unit}.")
        except Exception as e:
            print(f"Error setting measurement unit: {e}")

    def query_rs232_terminator(self):
        """
        Queries the current RS-232 terminator setting of the Keithley 6220.

        :return: The current RS-232 terminator setting (LF, CR, or CRLF), or None if an error occurs.
        """
        try:
            response = self.query_6220("SYST:COMM:SER:TERM?")
            print(f"RS-232 Terminator Setting: {response}")
            return response
        except Exception as e:
            print(f"Error querying RS-232 terminator setting: {e}")
            return None

    def set_rs232_terminator_to_lf(self):
        """
        Sets the RS-232 terminator of the Keithley 6220 to LF (Line Feed).
        This ensures consistency with GPIB communication.

        :return: True if successfully set, False otherwise.
        """
        try:
            # Send the command to set RS-232 terminator to LF
            self.send_command_to_6220("SYST:COMM:SER:TERM LF")

            # Verify the setting
            current_terminator = self.query_rs232_terminator()
            if current_terminator == "LF":
                print("RS-232 Terminator successfully set to LF.")
                return True
            else:
                print(f"Warning: RS-232 terminator not confirmed, received: {current_terminator}")
                return False
        except Exception as e:
            print(f"Error setting RS-232 terminator to LF: {e}")
            return False

    def set_buffer_size(self):
        """
        NOT called directly.
        Sets the buffer size for Differential Conductance based on self.total_points.
        Ensures the buffer is correctly allocated before starting the test.

        :return: True if buffer size is set successfully, False otherwise.
        """
        try:
            if self.total_points is None:
                print("Error: Total points not set. Run `set_differential_conductance_params()` first.")
                return False

            # Set buffer size using pre-calculated total points
            self.send_command_to_6220(f"TRAC:POIN {self.total_points}")
            # query the buffer size to verify
            if self.verify_buffer_size():
                print(f"Buffer size set to {self.total_points} points.")
                return True
            else:
                print("Error setting buffer size.")
                return False

        except Exception as e:
            print(f"Error setting buffer size: {e}")
            return False

    def verify_buffer_size(self):
        """
        Queries the buffer size from the 6220 and verifies it matches the expected self.total_points.

        :return: True if the buffer size matches, False otherwise.
        """
        try:
            # Ensure buffer size was set before verifying
            if self.total_points is None:
                print("Error: Total points not set. Run `set_differential_conductance_params()` first.")
                return False

            # Query the buffer size from the device
            response = self.query_6220("TRAC:POIN?")
            if response is None:
                print("Error querying buffer size.")
                return False

            queried_buffer_size = int(response)

            # Compare with expected size
            if queried_buffer_size == self.total_points:
                print(f"Buffer size verified successfully: {queried_buffer_size} points.")
                return True
            else:
                print(f"Warning: Expected {self.total_points}, but device reports {queried_buffer_size}.")
                return False

        except Exception as e:
            print(f"Error verifying buffer size: {e}")
            return False

    def initialize_differential_conductance(self):
        """
        Starts the Differential Conductance measurement if the device is already armed.

        Steps:
        1. Check if the 6220 is armed.
        2. If armed, send `INIT:IMM` to start measurement.

        :return: True if measurement starts successfully, False otherwise.
        """
        try:
            print("Initializing Differential Conductance Measurement...")

            # Step 1: Check if the device is armed
            if not self.check_arm_status():
                print("Device is not armed. Run `arm_device()` first.")
                return False

            # Step 2: Start the measurement
            self.send_command_to_6220("INIT:IMM")
            print("Differential Conductance Measurement Started.")

            return True

        except Exception as e:
            print(f"Error initializing Differential Conductance: {e}")
            return False

    def get_all_differential_conductance_data(self):
        """
        Retrieves all stored Differential Conductance readings from the 6220 buffer.
        Optimized for large datasets (up to 65,536 points), with buffer handling, retries, and timing diagnostics.

        :return:A raw data of readings if successful, None if an error occurs.
        """
        try:
            # Configure PyVISA for large data handling
            self.instrument.timeout = 1000  # Set timeout to 15s for long data transfers
            self.instrument.chunk_size = 1048576  # Increase buffer size to 1MB

            # Start timing the retrieval process
            start_time = time.time()

            # Use read_raw() instead of query() to avoid string overhead
            # self.instrument.write("TRAC:DATA?")
            # raw_data = self.instrument.read_raw()  # Reads raw binary data
            # Calculate time taken
            retrieval_time = time.time() - start_time

            # Decode response and process as NumPy array
            # response = raw_data.decode("ascii").strip()

            response = self.instrument.query("TRAC:DATA?").strip()
            print(f"the response is {response}")
            # Convert response into NumPy array
            # data_points = np.fromstring(response, sep=",", dtype=np.float64)


            print(f"Data retrieval took {retrieval_time:.3f} seconds.")

            # print(f"Successfully retrieved {len(data_points)} measurement points.")
            return response

        except ValueError as ve:
            print(f"Error processing TRAC:DATA? response: {ve}")
            return None
        except Exception as e:
            print(f"Error retrieving measurement data: {e}")
            return None

    def parse_iv_data(self, raw_data):
        """Parses raw device data into separate current (ADC) and voltage (VDC) arrays.

        :param raw_data: Raw data string from the device.
        :return: Tuple containing current and voltage arrays, or empty arrays if parsing fails.
        """
        try:
            readings = raw_data.split("#")  # ✅ Split data based on delimiter
            current_values = []
            voltage_values = []

            for entry in readings:
                # ✅ Extract values using regex
                voltage_matches = re.findall(r"([-+]?\d+\.\d+E[-+]?\d+)VDC", entry)
                current_matches = re.findall(r"([-+]?\d+\.\d+E[-+]?\d+)ADC", entry)

                if voltage_matches and current_matches:
                    voltage_values.append(float(voltage_matches[0]))
                    current_values.append(float(current_matches[0]))

            return current_values, voltage_values

        except Exception as e:
            print(f"Error parsing raw data: {e}")
            return [], []

    def set_output_low_floating(self):
        """
        Sets the Keithley 6220 output low to floating (`OUTP:LTEarth OFF`).
        Verifies the setting after applying.
        """
        if self.is_output_off():
            try:
                # Send command to float the output low
                self.send_command_to_6220("OUTP:LTEarth OFF")

                # Verify the setting
                response = self.query_6220("OUTP:LTEarth?")
                if response is None:
                    print("Error: Failed to query Output Low status.")
                    return False

                if response.upper() == "OFF":
                    print("Output Low successfully set to FLOATING.")
                    return True
                else:
                    print(f"Warning: Expected FLOATING (OFF), but received '{response}'.")
                    return False
            except Exception as e:
                print(f"Error setting Output Low to FLOATING: {e}")
                return False
        else:
            print("Output is ON. Cannot set Output Low to FLOATING.")
            return False

    def set_output_low_grounded(self):
        """
        Sets the Keithley 6220 output low to Earth Ground (`OUTP:LTEarth ON`).
        Verifies the setting after applying.
        """
        if self.is_output_off():
            try:
                # Send command to ground the output low
                self.send_command_to_6220("OUTP:LTEarth ON")

                # Verify the setting
                response = self.query_6220("OUTP:LTEarth?")
                if response is None:
                    print("Error: Failed to query Output Low status.")
                    return False

                if str(response) == "1":
                    print("Output Low successfully set to EARTH GROUND.")
                    return True
                else:
                    print(f"Warning: Expected EARTH GROUND (ON), but received '{response}'.")
                    return False
            except Exception as e:
                print(f"Error setting Output Low to EARTH GROUND: {e}")
                return False
        else:
            print("Output is ON. Cannot set Output Low to EARTH GROUND.")
            return False

    def query_output_low_setting(self):
        """
        Queries the Keithley 6220 to check whether the Output Low is floating or grounded.

        :return: "ON" (Earth Ground), "OFF" (Floating), or None if an error occurs.
        """
        try:
            response = self.query_6220("OUTP:LTEarth?")
            if response is None:
                print("Error: Failed to query Output Low setting.")
                return None

            response = str(response)
            if response in ["0", "1"]:
                print(f"Current Output Low Setting: {response}")
                self.output_low_status = response
                return response
            else:
                print(f"Unexpected response when querying Output Low: '{response}'")
                return None
        except Exception as e:
            print(f"Error querying Output Low setting: {e}")
            return None



    def query_diff_cond_data_type(self):
        """
        Parses FORM:ELEM? response into structured data based on selected format.

        :param data_points: NumPy array of retrieved measurement points.
        :return: Dictionary containing parsed data elements.
        """
        try:
            # Query the selected data format
            format_response = self.query_6220("FORM:ELEM?")
            # format_elements = format_response.split(",")

            # num_elements = len(format_elements)
            # if len(data_points) % num_elements != 0:
            #     print("Warning: Data length mismatch with format settings.")
            #     return None

            # Reshape data based on selected format
            # reshaped_data = data_points.reshape(-1, num_elements)
            #
            # # Store results in a dictionary
            # parsed_data = {format_elements[i]: reshaped_data[:, i] for i in range(num_elements)}
            #
            # print(f"Parsed {len(reshaped_data)} measurement points.")
            # return parsed_data
            print(f"The format response is {format_response}")
            return format_response

        except Exception as e:
            print(f"Error parsing TRAC:DATA? response: {e}")
            return None

    def enable_all_data_output(self):
        """
        Enables all data output elements for Differential Conductance measurements.
        (need to enable all data to have full access to the data for future use)
        :return: True if the command succeeds, False otherwise. None for error.
        """
        try:
            # Send the command to enable all data output elements
            self.send_command_to_6220("FORM:ELEM ALL")
            print("All data output elements enabled.")
            # todo: Verify the settings
            expected_response = "READ,UNIT,RNUM,TST,COMP,SOUR,AVOL"
            response = self.query_diff_cond_data_type()
            if response == expected_response:
                print("All data output elements verified.")
                return True
            else:
                print(f"Unexpected data output elements: {response}")
                return False
        except Exception as e:
            print(f"Error enabling all data output elements: {e}")
            return None

        #412: Diff. Conductance upranged