import csv
import os
import ntpath
import logging

from modules.filechecks import is_image_file, is_valid_filename
from variables import (
    valid_first_segment_first_char,
    valid_first_segment_other_chars,
    valid_id_initial_chars,
    valid_suffixes,
)


class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def validate_csv_to_report(input_csv, output_csv):
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    handler = LogCaptureHandler()
    logger.addHandler(handler)

    try:
        with open(input_csv, newline="", encoding="utf-8") as infile, \
             open(output_csv, "w", newline="", encoding="utf-8") as outfile:

            reader = csv.DictReader(infile)
            writer = csv.DictWriter(
                outfile,
                fieldnames=["FullName", "Filename", "Status", "Reason"]
            )
            writer.writeheader()

            for row in reader:
                full_path = row["FullName"]
                fname = ntpath.basename(full_path)

                handler.records.clear()

                if not is_image_file(fname):
                    writer.writerow({
                        "FullName": full_path,
                        "Filename": fname,
                        "Status": "skipped",
                        "Reason": "invalid file type",
                    })
                    continue

                valid, _ = is_valid_filename(
                    fname,
                    valid_first_segment_first_char,
                    valid_first_segment_other_chars,
                    valid_id_initial_chars,
                    valid_suffixes,
                )

                if valid:
                    writer.writerow({
                        "FullName": full_path,
                        "Filename": fname,
                        "Status": "valid",
                        "Reason": "",
                    })
                else:
                    reason = (
                        handler.records[-1].getMessage()
                        if handler.records
                        else "invalid filename"
                    )
                    writer.writerow({
                        "FullName": full_path,
                        "Filename": fname,
                        "Status": "invalid",
                        "Reason": reason,
                    })

    finally:
        logger.removeHandler(handler)


if __name__ == "__main__":
    validate_csv_to_report(
        input_csv="/Volumes/PD/PD-RK-KM-Restaurierung/Allgemein/Bildgebung/Projekte/2025_bura/S-Production-Import-Max-Ehrengruber_filelist_2026-01-22T1717.csv",
        output_csv="csv/S-Production-Import-Max-Ehrengruber_filelist_2026-01-22T1717_validation_report.csv",
    )
