import pyvisa


class Keithley2182AConnection:
    """
    A class to manage the connection to the Keithley 2182A Nanovoltmeter using PyVISA.
    """

    def __init__(self, address):
        """
        Initialize the Keithley 2182AConnection class.
        :param address: The VISA address of the device (e.g., "GPIB0::7::INSTR").
        """
        self.address = address
        self.instrument = None
        self.device_connected = False

    def connect(self):
        """
        Establish a connection to the Keithley 2182A.
        :return: A message indicating the connection status.
        """
        try:
            # Initialize the ResourceManager
            rm = pyvisa.ResourceManager()

            # Open the instrument connection
            self.instrument = rm.open_resource(self.address)

            # Query the device to verify the connection
            device_id = self.instrument.query("*IDN?")
            self.device_connected = True
            return f"Connected to: {device_id.strip()}"
        except pyvisa.VisaIOError as e:
            return f"Error connecting to device: {e}"

    def close_connection(self):
        """
        Close the connection to the instrument.
        """
        if self.instrument:
            self.instrument.close()
            self.instrument = None
            self.device_connected = False
            print("Connection closed.")
        else:
            print("No active connection to close.")

    def is_connected(self):
        """
        Check if the connection is active.
        :return: True if connected, False otherwise.
        """
        return self.instrument is not None

    def query(self, command):
        """
        Send a query to the instrument and return the response.
        :param command: The SCPI command to query.
        :return: The response from the instrument.
        """
        if self.is_connected():
            try:
                response = self.instrument.query(command)
                return response.strip()
            except Exception as e:
                return f"Query error: {e}"
        else:
            return "Not connected to the device."

    def write(self, command):
        """
        Send a command to the instrument.
        :param command: The SCPI command to write.
        :return: None
        """
        if self.is_connected():
            try:
                self.instrument.write(command)
                print(f"Command sent: {command}")
            except Exception as e:
                print(f"Write error: {e}")
        else:
            print("Not connected to the device.")
