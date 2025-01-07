import pyvisa


class Keithley6220:
    def __init__(self, address):
        """
        Core functionality for the Keithley 6220.
        :param address: VISA address of the device (e.g., "GPIB0::12::INSTR").
        """
        self.address = address
        self.instrument = None

    def connect(self):
        """
        Connect to the device via GPIB.
        :return: A string message indicating success or failure.
        """
        try:
            # Initialize the ResourceManager
            rm = pyvisa.ResourceManager()

            # Open the instrument connection
            self.instrument = rm.open_resource(self.address)

            # Query and return the device ID for confirmation
            device_id = self.instrument.query("*IDN?")
            return f"Connected to: {device_id}"
        except pyvisa.VisaIOError as e:
            return f"Error connecting to device: {e}"

    def disconnect(self):
        """
        Close the connection to the instrument.
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

