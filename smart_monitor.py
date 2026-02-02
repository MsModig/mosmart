#!/usr/bin/env python3
"""
MoSMART Monitor - S.M.A.R.T. Disk Monitoring Tool

Copyright (C) 2026 Magnus S. Modig

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import sys
from typing import Dict, List, Optional
from pySMART import Device, DeviceList


def format_power_on_time(hours: int) -> str:
    """
    Convert hours to a human-readable format.
    - For < 24 hours: Show decimal hours (e.g., "17.8 timer")
    - For ≥ 24 hours: Show years, months, days, hours breakdown
    """
    # For less than 24 hours, show decimal precision
    if hours < 24:
        return f"{hours:.1f} timer"
    
    # For 24+ hours, use standard breakdown
    years = hours // 8760  # 365 * 24
    remaining = hours % 8760
    months = remaining // 730  # ~30.4 * 24
    remaining = remaining % 730
    days = remaining // 24
    remaining_hours = remaining % 24
    
    parts = []
    if years > 0:
        parts.append(f"{years} år")
    if months > 0:
        parts.append(f"{months} md")
    if days > 0 or (years == 0 and months == 0):  # Always show days if no years/months
        parts.append(f"{days} d")
    if remaining_hours > 0 or len(parts) == 0:  # Always show hours if nothing else
        parts.append(f"{remaining_hours} t")
    
    return ", ".join(parts) + f" ({hours:,} timer totalt)"


def calculate_health_score(device: Device, mosmart188_penalty: int = 0, mosmart188_count: int = 0) -> Dict[str, any]:
    """
    Calculate a comprehensive health score (0-100) based on critical S.M.A.R.T. attributes.
    Uses industry-standard weighting from Backblaze, Google, and drive manufacturers.
    
    Args:
        device: pySMART Device object
        mosmart188_penalty: Health penalty from mosmart188_manager (-100 to 0)
        mosmart188_count: Restart count in last 24h (for display in components)
    
    Weights (SSD with wear data):
    - Reallocated sectors: 42%
    - Wear level (bytes written): 15%
    - Pending sectors: 12%
    - Temperature: 10%
    - Uncorrectable sectors: 8%
    - Command timeout: 5%
    - mosmart188 (instability): 5%
    - Age: 3%
    
    Weights (SSD without wear data):
    - Reallocated sectors: 45%
    - Pending sectors: 15%
    - SMART read errors: 10%
    - Uncorrectable sectors: 10%
    - Command timeout: 5%
    - SMART read errors: 5%
    - Temperature: 10%
    - Age: 5%
    
    Weights (HDD):
    - Reallocated sectors: 40%
    - Pending sectors: 15%
    - SMART read errors: 10%
    - Age: 10% (mechanical wear is critical)
    - Uncorrectable sectors: 10%
    - Command timeout: 5%
    - Temperature: 10%
    
    Returns dict with total score and component scores.
    """
    if not device.attributes:
        return {'total': None, 'components': {}}
    
    # Extract critical attribute values
    def get_attr_value(attr_id: int) -> int:
        attr = next((a for a in device.attributes if a and a.num == attr_id), None)
        if attr and attr.raw:
            try:
                value = int(str(attr.raw).split()[0])
                # Detect sentinel/invalid values (common with USB adapters)
                # 2^32-1, 2^64-1, or other impossibly high values
                if value >= 4294967295:  # UINT32_MAX or higher
                    return 0
                return value
            except (ValueError, TypeError):
                return 0
        return 0
    
    realloc = get_attr_value(5)      # Reallocated Sectors Count
    pending = get_attr_value(197)    # Current Pending Sector Count
    uncorr = get_attr_value(198)     # Uncorrectable Sector Count
    timeout = get_attr_value(188)    # Command Timeout
    
    # Handle Power On Hours (ID 9) - some disks report seconds instead of hours
    power_on_hours = 0
    attr_9 = next((a for a in device.attributes if a and a.num == 9), None)
    if attr_9:
        try:
            raw_str = str(attr_9.raw).strip()
            
            # Check attribute name to determine if it's seconds or hours
            if attr_9.name and 'Second' in attr_9.name:
                # Power_On_Seconds - handle different formats
                if 'h+' in raw_str and 'm+' in raw_str and 's' in raw_str:
                    # Format: "0h+17m+48s" or "123h+45m+12s"
                    import re
                    match = re.match(r'(\d+)h\+(\d+)m\+(\d+)s', raw_str)
                    if match:
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        seconds = int(match.group(3))
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        power_on_hours = total_seconds // 3600
                else:
                    # Plain number format
                    seconds = int(raw_str.split()[0])
                    if seconds < 4294967295:  # Valid value
                        power_on_hours = seconds // 3600
            else:
                # Power_On_Hours - use directly
                power_on_hours = int(raw_str.split()[0])
                if power_on_hours >= 4294967295:
                    power_on_hours = 0
        except (ValueError, TypeError, AttributeError):
            power_on_hours = 0
    
    power_cycles = get_attr_value(12)    # Power Cycle Count
    
    # Score calculation functions
    def score_reallocated(count: int) -> int:
        """Reallocated sectors score (50% weight)"""
        if count == 0:
            return 100
        elif count <= 10:
            return 90
        elif count <= 100:
            return 70
        elif count <= 500:
            return 40
        elif count <= 1000:
            return 20
        elif count <= 5000:
            return 5
        elif count <= 10000:
            return -10
        elif count <= 20000:
            return -50
        else:
            return -100  # Seagate ST2000DM001 territory
    
    def score_pending(count: int) -> int:
        """Pending sectors score (25% weight) - Higher weight due to immediate danger"""
        if count == 0:
            return 100
        elif count == 1:
            return 85
        elif count <= 5:
            return 60
        elif count <= 20:
            return 30
        elif count <= 100:
            return 10
        elif count <= 300:
            return -30
        elif count <= 500:
            return -70
        else:
            return -100  # >500 = Critical zombie territory
    
    def score_uncorrectable(count: int) -> int:
        """Uncorrectable sectors score (10% weight)
        Uncorrectable = permanent data loss, extremely serious"""
        if count == 0:
            return 100
        elif count == 1:
            return 60  # Warning, but not critical yet
        elif count <= 5:
            return 20  # Serious
        elif count <= 10:
            return -30  # Critical
        elif count <= 20:
            return -70  # Terminal
        else:
            return -100  # Zombie - permanent data loss
    
    def score_timeout(count: int) -> int:
        """Command timeout score (5-10% weight)"""
        if count == 0:
            return 100
        elif count <= 5:
            return 70
        elif count <= 50:
            return 40
        elif count <= 200:
            return 20
        else:
            return 0
    
    def score_mosmart188(penalty: int) -> int:
        """
        mosmart188 - Disk Instability Score (Virtual SMART Attribute)
        
        Accepts a pre-calculated penalty from mosmart188_manager (-100 to 0).
        The penalty represents disk instability over time with:
        - Sliding 24h window
        - Asymmetric degradation/recovery
        - Lock mechanism during instability
        
        This function converts the penalty to a health score component.
        
        Args:
            penalty: Health penalty from mosmart188_manager (-100 to 0)
        
        Returns:
            Health score contribution (can be negative for severe issues)
        """
        # Penalty is already calculated by mosmart188_manager
        # Just convert it to the score format expected by health calculation
        # penalty = 0 → score = 100 (perfect)
        # penalty = -100 → score = -100 (terminal)
        return 100 + penalty
    
    def score_age(hours: int, is_ssd: bool = False) -> int:
        """
        Age score (10% weight)
        SSD and HDD have different expected lifespans
        """
        if is_ssd:
            # SSDs: Expected 5-10 years of heavy use
            years = hours / 8760
            if years < 3:
                return 100
            elif years < 5:
                return 90
            elif years < 7:
                return 75
            elif years < 10:
                return 50
            else:
                return 25
        else:
            # HDDs: Expected 3-5 years, some last 10+
            years = hours / 8760
            if years < 2:
                return 100
            elif years < 3:
                return 90
            elif years < 5:
                return 70
            elif years < 7:
                return 50
            elif years < 10:
                return 30
            else:
                return 10  # Ancient but might be fine if no bad sectors
    
    def score_power_cycles(cycles: int) -> int:
        """
        Power cycle score for HDD (10% weight)
        Mechanical parts wear from start/stop cycles
        """
        if cycles == 0:
            return 100  # No data or brand new
        elif cycles < 1000:
            return 100  # Normal desktop/laptop usage
        elif cycles < 5000:
            return 90  # Frequent reboots
        elif cycles < 10000:
            return 80  # Heavy use
        elif cycles < 20000:
            return 70
        elif cycles < 50000:
            return 50  # Very heavy cycling
        else:
            return 30  # Extreme usage pattern
    
    def score_temperature(temp: int, is_ssd: bool = False) -> int:
        """
        Temperature score (5% weight)
        Different thresholds for SSD vs HDD
        """
        if temp is None or temp == 0:
            return 100  # No temp data, assume OK
        
        if is_ssd:
            # SSDs can run hotter
            if temp < 40:
                return 100
            elif temp < 50:
                return 90
            elif temp < 60:
                return 70
            elif temp < 70:
                return 40
            else:
                return 10
        else:
            # HDDs prefer cooler temps
            if temp < 35:
                return 100
            elif temp < 40:
                return 90
            elif temp < 45:
                return 70
            elif temp < 50:
                return 40
            else:
                return 10
    
    def score_wear(bytes_written: int, capacity_bytes: int) -> int:
        """
        SSD wear score based on total bytes written vs rated endurance
        Typical SSD endurance: 150-600 TBW per TB capacity
        Budget SSDs (like Crucial BX500): ~150-200 TBW per TB
        """
        if bytes_written is None or bytes_written == 0:
            return 100  # No data available
        
        if capacity_bytes is None or capacity_bytes == 0:
            return 100  # Can't calculate without capacity
        
        # Estimate rated endurance (TBW) based on capacity
        # Conservative estimate: 200 TBW per TB for budget SSDs
        capacity_tb = capacity_bytes / (1024**4)  # Convert to TB
        rated_tbw = capacity_tb * 200  # 200 TBW per TB
        
        # Calculate wear percentage
        written_tb = bytes_written / (1024**4)
        wear_percent = (written_tb / rated_tbw) * 100
        
        # Score based on wear level
        if wear_percent < 10:
            return 100  # Like new
        elif wear_percent < 25:
            return 95
        elif wear_percent < 50:
            return 85
        elif wear_percent < 75:
            return 70
        elif wear_percent < 90:
            return 50
        elif wear_percent < 100:
            return 25
        elif wear_percent < 120:
            return 10  # Over rated endurance but still working
        else:
            return 0  # Way past rated endurance
    
    def score_lifetime_remaining(percent_remaining: int) -> float:
        """
        SMART ID 202 (Percent_Lifetime_Remain) penalty
        - 21-100%: 0 penalty
        - 11-20%: linear penalty up to 10 points
        - 0-10%: exponential penalty up to 35 points (exponent 2)
        """
        if percent_remaining is None:
            return 0.0

        if percent_remaining >= 21:
            return 0.0
        if percent_remaining >= 11:
            return min(10.0, ((20 - percent_remaining) / 9) * 10)

        ratio = (10 - percent_remaining) / 10  # 0..1
        return min(35.0, 10.0 + (35.0 - 10.0) * (ratio ** 2))

    # Detect if SSD (simple heuristic: check interface and model name)
    is_ssd = False
    if device.model:
        model_lower = device.model.lower()
        is_ssd = 'ssd' in model_lower or 'nvme' in model_lower or 'bx500' in model_lower or 'crucial' in model_lower
    
    # Get bytes written for SSDs (attribute 241 or 247)
    bytes_written = None
    if is_ssd and device.attributes:
        bytes_attr = next((a for a in device.attributes if a and hasattr(a, 'num') and a.num in [241, 247]), None)
        if bytes_attr:
            try:
                raw_value = int(bytes_attr.raw)
                # Attribute 247 is typically in pages (4KB for Crucial)
                if bytes_attr.num == 247:
                    bytes_written = raw_value * 4096
                # Attribute 241 is in LBAs (512 bytes)
                elif bytes_attr.num == 241:
                    bytes_written = raw_value * 512
            except (ValueError, TypeError):
                pass

    # Get lifetime remaining for SSDs (SMART ID 202)
    lifetime_remaining = None
    if is_ssd and device.attributes:
        lifetime_attr = next((a for a in device.attributes if a and hasattr(a, 'num') and a.num == 202), None)
        if lifetime_attr and lifetime_attr.raw:
            try:
                raw_value = int(str(lifetime_attr.raw).split()[0])
                if raw_value >= 4294967295:
                    raw_value = 0

                attr_name = (lifetime_attr.name or '').lower()
                if 'percent_used' in attr_name:
                    lifetime_remaining = 100 - raw_value
                else:
                    lifetime_remaining = raw_value

                lifetime_remaining = max(0, min(100, lifetime_remaining))
            except (ValueError, TypeError):
                pass
    
    # Get capacity in bytes
    capacity_bytes = None
    if device.capacity:
        # Parse capacity string like "480 GB" or "1.0 TB"
        try:
            cap_str = str(device.capacity).upper().replace(',', '')
            if 'TB' in cap_str:
                capacity_bytes = int(float(cap_str.split()[0]) * (1024**4))
            elif 'GB' in cap_str:
                capacity_bytes = int(float(cap_str.split()[0]) * (1024**3))
        except (ValueError, TypeError, IndexError):
            pass
    
    # Calculate component scores
    realloc_score = score_reallocated(realloc)
    pending_score = score_pending(pending)
    uncorr_score = score_uncorrectable(uncorr)
    timeout_score = score_timeout(timeout)
    mosmart188_score = score_mosmart188(mosmart188_penalty)
    age_score = score_age(power_on_hours, is_ssd)
    temp_score = score_temperature(device.temperature, is_ssd)
    power_cycles_score = score_power_cycles(power_cycles)
    wear_score = score_wear(bytes_written, capacity_bytes) if is_ssd else None
    lifetime_penalty = score_lifetime_remaining(lifetime_remaining) if is_ssd else 0.0
    
    # Weighted total (can go negative for zombie disks)
    # Different weights for SSD vs HDD
    if is_ssd:
        # SSD: Include wear score if available, reduce age weight
        if wear_score is not None:
            # With wear data: pending sectors critical (25%), reallocated reduced
            total_score = (
                realloc_score * 0.35 +
                pending_score * 0.25 +
                wear_score * 0.15 +
                temp_score * 0.10 +
                uncorr_score * 0.08 +
                mosmart188_score * 0.05 +
                timeout_score * 0.05 +
                age_score * 0.02
            ) - lifetime_penalty
            weights = {
                'reallocated': '35%',
                'pending': '25%',
                'wear': '15%',
                'temperature': '10%',
                'uncorrectable': '8%',
                'mosmart188': '5%',
                'timeout': '5%',
                'age': '2%'
            }
        else:
            # Without wear data: pending sectors critical (25%)
            total_score = (
                realloc_score * 0.35 +
                pending_score * 0.25 +
                mosmart188_score * 0.10 +
                uncorr_score * 0.10 +
                temp_score * 0.10 +
                timeout_score * 0.05 +
                age_score * 0.05
            ) - lifetime_penalty
            weights = {
                'reallocated': '35%',
                'pending': '25%',
                'mosmart188': '10%',
                'uncorrectable': '10%',
                'temperature': '10%',
                'timeout': '5%',
                'age': '5%'
            }
    else:
        # HDD: Pending sectors matter more (active degradation) than reallocated (solved problems)
        total_score = (
            realloc_score * 0.30 +
            pending_score * 0.25 +
            mosmart188_score * 0.10 +
            power_cycles_score * 0.10 +
            uncorr_score * 0.10 +
            age_score * 0.05 +
            timeout_score * 0.05 +
            temp_score * 0.05
        )
        weights = {
            'reallocated': '30%',
            'pending': '25%',
            'mosmart188': '10%',
            'power_cycles': '10%',
            'uncorrectable': '10%',
            'age': '5%',
            'timeout': '5%',
            'temperature': '5%'
        }
    
    components = {
        'reallocated': {'value': realloc, 'score': realloc_score, 'weight': weights['reallocated']},
        'pending': {'value': pending, 'score': pending_score, 'weight': weights['pending']},
        'uncorrectable': {'value': uncorr, 'score': uncorr_score, 'weight': weights['uncorrectable']},
        'timeout': {'value': timeout, 'score': timeout_score, 'weight': weights['timeout']},
        'mosmart188': {'value': mosmart188_count, 'score': mosmart188_score, 'weight': weights.get('mosmart188', '0%')},
        'age': {'value': power_on_hours, 'score': age_score, 'weight': weights['age']},
        'temperature': {'value': device.temperature, 'score': temp_score, 'weight': weights['temperature']}
    }
    
    # Add power_cycles component for HDDs
    if not is_ssd and 'power_cycles' in weights:
        components['power_cycles'] = {
            'value': power_cycles,
            'score': power_cycles_score,
            'weight': weights['power_cycles']
        }
    
    # Add wear component for SSDs if available
    if is_ssd and wear_score is not None and 'wear' in weights:
        components['wear'] = {
            'value': bytes_written,
            'score': wear_score,
            'weight': weights['wear']
        }

    # Add lifetime remaining component for SSDs if available (penalty only)
    if is_ssd and lifetime_remaining is not None:
        components['lifetime_remaining'] = {
            'value': lifetime_remaining,
            'score': round(-lifetime_penalty, 2),
            'weight': 'penalty'
        }
    
    return {
        'total': min(100, round(total_score)),  # Cap at 100 max
        'is_ssd': is_ssd,
        'components': components
    }


def format_health_rating(score: int) -> str:
    """Get a textual rating based on health score"""
    if score >= 95:
        return "🔵 UTMERKET"
    elif score >= 80:
        return "🟢 God"
    elif score >= 60:
        return "🟡 Akseptabel"
    elif score >= 40:
        return "🟠 Advarsel"
    elif score >= 20:
        return "🔴 Dårlig"
    elif score >= 0:
        return "🔴 KRITISK"
    elif score >= -50:
        return "💀 DØD"
    else:
        return "🧟 ZOMBIE (Seagate-special)"


def detect_ghost_drive_condition(device: Device, health_components: Dict) -> Dict[str, any]:
    """
    Detect Ghost Drive Condition (GDC) - a known issue with certain Seagate drives.
    
    GDC indicators:
    1. Seagate ST2000DM001 series (most common)
    2. Extremely high reallocated sector count (>10,000)
    3. Slow response times / command timeouts
    4. Drive appears functional but with severe degradation
    
    Returns dict with:
    - has_gdc: bool
    - confidence: str ('high', 'medium', 'low')
    - indicators: list of strings
    """
    indicators = []
    confidence = 'none'
    
    if not device or not device.model:
        return {'has_gdc': False, 'confidence': 'none', 'indicators': []}
    
    model = device.model.upper()
    realloc = health_components.get('reallocated', {}).get('value', 0)
    timeout = health_components.get('timeout', {}).get('value', 0)
    
    # Check 1: Known problematic models
    gdc_models = [
        'ST2000DM001',  # Most notorious
        'ST3000DM001',  # Also affected
        'ST1000DM003',  # Common in series
    ]
    
    is_gdc_model = any(m in model for m in gdc_models)
    if is_gdc_model:
        indicators.append(f"Known GDC-prone model: {device.model}")
        confidence = 'high'
    
    # Check 2: Excessive reallocated sectors
    if realloc > 10000:
        indicators.append(f"Extreme reallocated sectors: {realloc:,}")
        if confidence == 'none':
            confidence = 'medium'
        elif confidence == 'medium':
            confidence = 'high'
    elif realloc > 5000:
        indicators.append(f"Very high reallocated sectors: {realloc:,}")
        if confidence == 'none':
            confidence = 'low'
    
    # Check 3: Command timeouts (slow response)
    if timeout > 100:
        indicators.append(f"Excessive command timeouts: {timeout}")
        if confidence == 'none':
            confidence = 'low'
        elif confidence == 'low':
            confidence = 'medium'
    
    # Check 4: Seagate + high realloc combo (medium confidence even without exact model)
    if 'SEAGATE' in model or 'ST' in model[:2]:
        if realloc > 1000 and confidence == 'none':
            indicators.append("Seagate drive with high reallocated sectors")
            confidence = 'low'
    
    has_gdc = len(indicators) > 0 and confidence in ['medium', 'high']
    
    return {
        'has_gdc': has_gdc,
        'confidence': confidence,
        'indicators': indicators
    }


class SMARTMonitor:
    """Main class for monitoring S.M.A.R.T. data from drives"""
    
    def __init__(self):
        self.devices: List[Device] = []
    
    def scan_devices(self) -> None:
        """Scan for all available storage devices"""
        try:
            devlist = DeviceList()
            self.devices = [dev for dev in devlist.devices if dev is not None]
            print(f"Found {len(self.devices)} storage device(s)")
        except Exception as e:
            print(f"Error scanning devices: {e}", file=sys.stderr)
            sys.exit(1)
    
    def get_device(self, device_path: str) -> Optional[Device]:
        """Get a specific device by path"""
        try:
            device = Device(device_path)
            return device if device.assessment else None
        except Exception as e:
            print(f"Error accessing device {device_path}: {e}", file=sys.stderr)
            return None
    
    def display_device_info(self, device: Device) -> None:
        """Display basic information about a device"""
        print(f"\n{'='*60}")
        print(f"Device: {device.name}")
        print(f"{'='*60}")
        print(f"Model:        {device.model}")
        print(f"Serial:       {device.serial}")
        print(f"Capacity:     {device.capacity}")
        print(f"Interface:    {device.interface}")
        print(f"Assessment:   {device.assessment}")
        print(f"Temperature:  {device.temperature}°C" if device.temperature else "Temperature:  N/A")
        # Get power on hours (attribute ID 9)
        power_on_attr = next((a for a in device.attributes if a and a.num == 9), None) if device.attributes else None
        if power_on_attr:
            try:
                hours = int(str(power_on_attr.raw).split()[0])
                print(f"Power On:     {format_power_on_time(hours)}")
            except (ValueError, TypeError):
                print(f"Power On:     {power_on_attr.raw}")
        else:
            print(f"Power On:     N/A")
    
    def display_smart_attributes(self, device: Device) -> None:
        """Display S.M.A.R.T. attributes for a device"""
        if not device.attributes:
            print("No S.M.A.R.T. attributes available")
            return
        
        print(f"\nS.M.A.R.T. Attributes:")
        print(f"{'ID':<5} {'Attribute Name':<30} {'Value':<7} {'Worst':<7} {'Thresh':<7} {'Raw':<15} {'Status'}")
        print("-" * 95)
        
        for attr in device.attributes:
            if attr:
                try:
                    # Only compare if threshold > 0 (meaningful threshold)
                    thresh = int(attr.thresh)
                    val = int(attr.value)
                    if thresh > 0:
                        status = "FAIL" if val < thresh else "OK"
                    else:
                        status = "OK"  # Attributes with thresh=0 are informational only
                    print(f"{attr.num:<5} {attr.name:<30} {attr.value:<7} {attr.worst:<7} {attr.thresh:<7} {str(attr.raw):<15} {status}")
                except (ValueError, TypeError):
                    pass  # Skip attributes with non-numeric values
    
    def check_health(self, device: Device) -> Dict[str, any]:
        """Analyze device health and return critical information"""
        health_info = {
            'status': device.assessment,
            'warnings': [],
            'critical': []
        }
        
        if not device.attributes:
            return health_info
        
        # Critical attributes to monitor
        critical_attrs = {
            5: 'Reallocated Sectors Count',
            187: 'Reported Uncorrectable Errors',
            188: 'Command Timeout',
            196: 'Reallocation Event Count',
            197: 'Current Pending Sector Count',
            198: 'Uncorrectable Sector Count'
        }
        
        for attr_id, attr_name in critical_attrs.items():
            # Find attribute by ID
            attr = next((a for a in device.attributes if a and a.num == attr_id), None)
            if attr and attr.raw and int(str(attr.raw).split()[0]) > 0:
                health_info['warnings'].append(f"{attr_name}: {attr.raw}")
        
        # Check temperature
        if device.temperature and device.temperature > 50:
            health_info['warnings'].append(f"High temperature: {device.temperature}°C")
        
        # Check if any attribute is below threshold
        for attr in device.attributes:
            if attr and hasattr(attr, 'value') and hasattr(attr, 'thresh'):
                try:
                    # Only flag as critical if value is below threshold AND threshold > 0
                    val = int(attr.value)
                    thresh = int(attr.thresh)
                    if thresh > 0 and val < thresh:
                        health_info['critical'].append(f"{attr.name} (ID {attr.num}): Value {attr.value} below threshold {attr.thresh}")
                except (ValueError, TypeError):
                    pass  # Skip if values can't be converted to int
        
        return health_info
    
    def display_health_summary(self, device: Device) -> None:
        """Display health summary for a device"""
        health = self.check_health(device)
        health_score_data = calculate_health_score(device)
        
        print(f"\n{'='*60}")
        print(f"HELSEOPPSUMMERING")
        print(f"{'='*60}")
        
        # Display health score if available
        if health_score_data['total'] is not None:
            score = health_score_data['total']
            rating = format_health_rating(score)
            drive_type = "SSD" if health_score_data.get('is_ssd') else "HDD"
            print(f"\n🧠 HEALTH SCORE: {score}/100 - {rating} ({drive_type})")
            
            print(f"\nKomponenter (vektet):")
            for name, data in health_score_data['components'].items():
                name_display = {
                    'reallocated': 'Reallokerte sektorer',
                    'pending': 'Ventende sektorer',
                    'uncorrectable': 'Urettbare sektorer',
                    'timeout': 'Kommando timeouts',
                    'age': 'Alder (timer)',
                    'temperature': 'Temperatur (°C)'
                }[name]
                
                # Format value display
                if name == 'age':
                    hours = data['value']
                    years = hours / 8760
                    val_display = f"{hours:>8,} ({years:.1f} år)"
                elif name == 'temperature':
                    val_display = f"{data['value'] if data['value'] else 'N/A':>8}"
                else:
                    val_display = f"{data['value']:>8,}"
                
                print(f"  • {name_display:<25} {val_display} → score {data['score']:>4} (vekt {data['weight']})")
        
        print(f"\nS.M.A.R.T. Status: {health['status']}")
        
        if health['critical']:
            print(f"\n⚠️  KRITISKE PROBLEMER:")
            for issue in health['critical']:
                print(f"  - {issue}")
        
        if health['warnings']:
            print(f"\n⚠️  Advarsler:")
            for warning in health['warnings']:
                print(f"  - {warning}")
        
        if not health['critical'] and not health['warnings'] and health_score_data['total'] and health_score_data['total'] >= 95:
            print("\n✓ Ingen problemer oppdaget - disken er i utmerket stand!")
        elif not health['critical'] and not health['warnings']:
            print("\n✓ Ingen akutte problemer oppdaget")
        
        # Add recommendation based on score
        if health_score_data['total'] is not None:
            score = health_score_data['total']
            print(f"\nAnbefaling:")
            if score >= 80:
                print("  ✓ Disken er i god stand. Fortsett normal bruk.")
            elif score >= 60:
                print("  ⚠ Overvåk disken regelmessig. Vurder backup.")
            elif score >= 40:
                print("  ⚠ Økt risiko for feil. Sikre data med backup NÅ.")
            elif score >= 0:
                print("  🔴 KRITISK: Bytt ut disken ASAP! Data er i fare!")
            else:
                print("  💀 DISKEN ER DØD/DØENDE. Bytt ut UMIDDELBART!")
                print("  🔥 Bruk kun til ikke-viktige data eller kast den.")
        
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='S.M.A.R.T. Monitor - Monitor hard drive health',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all available storage devices'
    )
    
    parser.add_argument(
        '-d', '--device',
        type=str,
        help='Specify device to monitor (e.g., /dev/sda)'
    )
    
    parser.add_argument(
        '-a', '--attributes',
        action='store_true',
        help='Show detailed S.M.A.R.T. attributes'
    )
    
    parser.add_argument(
        '--health',
        action='store_true',
        help='Show health summary only'
    )
    
    args = parser.parse_args()
    
    monitor = SMARTMonitor()
    
    # List all devices
    if args.list:
        monitor.scan_devices()
        for dev in monitor.devices:
            print(f"\n{dev.name}: {dev.model} ({dev.capacity})")
        return
    
    # Monitor specific device
    if args.device:
        device = monitor.get_device(args.device)
        if not device:
            print(f"Could not access device {args.device}")
            sys.exit(1)
        
        if args.health:
            monitor.display_health_summary(device)
        else:
            monitor.display_device_info(device)
            if args.attributes:
                monitor.display_smart_attributes(device)
            monitor.display_health_summary(device)
    else:
        # No device specified, scan and show all
        monitor.scan_devices()
        for dev in monitor.devices:
            monitor.display_device_info(dev)
            if args.attributes:
                monitor.display_smart_attributes(dev)
            monitor.display_health_summary(dev)


if __name__ == '__main__':
    main()
