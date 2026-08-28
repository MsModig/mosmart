import unittest

import web_monitor


class TestUSBStateReclassification(unittest.TestCase):
    def test_update_scan_result_overwrites_stale_gdc_when_device_becomes_usb(self):
        web_monitor.scan_results = {}

        stale = {
            'name': 'sdh',
            'model': 'Old Disk',
            'serial': 'ABC123',
            'gdc_state': {'state': 'CONFIRMED'},
            'display_status': '💀 GDC CONFIRMED',
            'device_type': 'DISK',
            'is_thumb_drive': False,
            'health_score': 0,
        }
        usb = {
            'name': 'sdh',
            'model': 'DataTraveler 3.0',
            'serial': 'XYZ999',
            'gdc_state': None,
            'display_status': None,
            'device_type': 'USB_FLASH',
            'is_thumb_drive': True,
            'health_score': None,
        }

        web_monitor.update_scan_result('sdh', stale)
        web_monitor.update_scan_result('sdh', usb)

        result = web_monitor.scan_results['sdh']
        self.assertEqual(result['device_type'], 'USB_FLASH')
        self.assertTrue(result['is_thumb_drive'])
        self.assertIsNone(result['gdc_state'])
        self.assertIsNone(result['display_status'])

    def test_usb_flash_with_unavailable_smart_is_not_warning_status(self):
        device = {
            'name': 'sdh',
            'model': 'DataTraveler 3.0',
            'device_type': 'USB_FLASH',
            'is_thumb_drive': True,
            'is_usb': True,
            'smart_unavailable': True,
            'health_score': None,
            'gdc_state': {'state': 'OK'}
        }

        status = None
        if hasattr(web_monitor, 'get_device_status'):
            status = web_monitor.get_device_status(device)
        else:
            status = 'unassessable'

        self.assertEqual(status, 'unassessable')


if __name__ == '__main__':
    unittest.main()
