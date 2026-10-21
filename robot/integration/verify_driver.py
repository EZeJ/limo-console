#!/usr/bin/env python3
"""Source contract check. This does not prove physical stopping performance."""
import argparse,json
from pathlib import Path

def check(root):
    root=Path(root)
    source=(root/'limo_base/src/limo_driver.cpp').read_text()
    header=(root/'limo_base/include/limo_base/limo_driver.h').read_text()
    return {'command_timeout_350ms':'milliseconds(350)' in source and 'command_watchdog_' in source,
            'command_receipt_refresh':'last_command_ = std::chrono::steady_clock::now();' in source,
            'yaw_wrap':'std::remainder(present_theta_ - last_theta_, 360.0)' in source,
            'yaw_initialized':'imu_initialized_ = false' in header,
            'physical_watchdog_test':'not performed by source inspection'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');args=parser.parse_args()
    result=check(args.source);print(json.dumps(result,indent=2))
    raise SystemExit(0 if all(value is True for key,value in result.items() if key!='physical_watchdog_test') else 1)
if __name__=='__main__':main()
