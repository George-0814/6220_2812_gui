import pyvisa


class Keithley6220:
    def __init__(self, address):
        """
        Core functionality for the Keithley 6220.
        :param address: VISA address of the device (e.g., "GPIB0::12::INSTR").
        """
        self.address = address
        self.instrument = None

    def send_command_to_6220(self, command: str):
        """Send a command to the 6220 with no response expected."""
        try:
            self.instrument.write(command)
            print(f"Command sent: {command}")
        except Exception as e:
            print(f"Error sending command: {e}")

    def query_6220(self, command: str):
        """Send a query command to the 6220 and return the response."""
        try:
            response = self.instrument.query(command)
            print(f"Query sent: {command}, Response: {response.strip()}")
            return response.strip()
        except Exception as e:
            print(f"Error querying command: {e}")
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
            response = self.query_6220("SYST:ERR?")
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