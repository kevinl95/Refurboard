import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothHidDevice
import android.bluetooth.BluetoothHidDeviceAppQosSettings
import android.bluetooth.BluetoothHidDeviceAppSdpSettings
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {
    private lateinit var bluetoothAdapter: BluetoothAdapter
    private lateinit var bluetoothHidDevice: BluetoothHidDevice

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // Your UI code here
        }

        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        bluetoothAdapter = bluetoothManager.adapter

        if (!bluetoothAdapter.isEnabled) {
            val enableBtIntent = Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)
            startActivityForResult(enableBtIntent, REQUEST_ENABLE_BT)
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.BLUETOOTH_CONNECT), REQUEST_BLUETOOTH_CONNECT)
        } else {
            setupBluetoothHidDevice()
        }
    }

    private fun setupBluetoothHidDevice() {
        try {
            val hidManager = getSystemService("bluetooth_hid_device") as BluetoothHidDevice
            bluetoothHidDevice = hidManager

            val sdpSettings = BluetoothHidDeviceAppSdpSettings(
                "Refurboard",
                "Open-source interactive whiteboard",
                "RefurboardProject",
                BluetoothHidDevice.SUBCLASS1_COMBO,
                byteArrayOf(0x05, 0x01, 0x09, 0x02, 0xA1.toByte(), 0x01, 0x09, 0x01, 0xA1.toByte(), 0x00, 0x05, 0x09, 0x19, 0x01, 0x29, 0x01, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95.toByte(), 0x03, 0x81.toByte(), 0x02, 0x75, 0x05, 0x95.toByte(), 0x01, 0x81.toByte(), 0x01, 0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x15, 0x81.toByte(), 0x25, 0x7F, 0x75, 0x08, 0x95.toByte(), 0x02, 0x81.toByte(), 0x06, 0xC0.toByte(), 0xC0.toByte())
            )

            val qosSettings = BluetoothHidDeviceAppQosSettings(
                BluetoothHidDeviceAppQosSettings.SERVICE_BEST_EFFORT,
                800,
                9,
                0,
                11250,
                BluetoothHidDeviceAppQosSettings.MAX
            )

            bluetoothHidDevice.registerApp(sdpSettings, qosSettings, null, null, hidCallback)
        } catch (e: SecurityException) {
            e.printStackTrace()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_BLUETOOTH_CONNECT) {
            if ((grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED)) {
                setupBluetoothHidDevice()
            } else {
                // Permission denied, handle accordingly
            }
        }
    }

    private val hidCallback = object : BluetoothHidDevice.Callback() {
        override fun onAppStatusChanged(pluggedDevice: BluetoothDevice?, registered: Boolean) {
            if (registered) {
                // App registered successfully
            } else {
                // App registration failed
            }
        }

        override fun onConnectionStateChanged(device: BluetoothDevice?, state: Int) {
            if (state == BluetoothHidDevice.STATE_CONNECTED) {
                // Device connected
            } else if (state == BluetoothHidDevice.STATE_DISCONNECTED) {
                // Device disconnected
            }
        }
    }

    companion object {
        private const val REQUEST_ENABLE_BT = 1
        private const val REQUEST_BLUETOOTH_CONNECT = 2
    }
}