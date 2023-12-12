import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Union, IO

BUSINESS_SURVEY_KEY = "business"
NON_BUSINESS_SURVEY_KEY = "non-business"

# Initialize variables to store feedback data and earliest date
FEEDBACK_BY_SURVEY_TYPE = {
    BUSINESS_SURVEY_KEY: [],
    NON_BUSINESS_SURVEY_KEY: [],
}

YELLOW_COLOUR = "\033[93m"
GREEN_COLOUR = "\033[92m"
RED_COLOUR = "\033[91m"
ENDC = "\033[0m"


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as stream:
        try:
            return json.load(stream)
        except json.decoder.JSONDecodeError as ex:
            print(f"Error reading JSON file {file_path}: {ex}")

            return None


@dataclass
class OutputField:
    name: Union[str, list[str]]
    default_value: str = ""


@dataclass
class Config:
    aggregated_file_prefix: str
    source_folder: str
    output_fields: list[OutputField]

    def __post_init__(self):

        # Check if the specified source folder exists
        if not os.path.exists(self.source_folder):
            print(f"The specified source folder '{self.source_folder}' does not exist!")
            sys.exit(1)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        output_fields = data.pop("output_fields")
        return cls(
            **data,
            output_fields=[OutputField(**item) for item in output_fields],
        )


# LOAD CONFIG

CONFIG = Config.from_dict(read_json_file("CONFIG.json"))

# PROCESS FEEDBACK


def process_feedback_file(*, feedback_file):
    """
    Process a single feedback file, check validity, update feedback_data, and determine the earliest date.
    """
    filename = os.path.basename(feedback_file)

    # Skip files with aggregated feedback in the filename
    if CONFIG.aggregated_file_prefix.lower() in filename.lower():
        return None

    data = read_json_file(feedback_file)

    # Check if the file contains valid JSON data
    if data is None:
        print(f"Warning: {feedback_file} is not valid JSON and will be skipped.")
        return None

    try:
        if "qid" in data["survey_metadata"]:
            key = NON_BUSINESS_SURVEY_KEY
        elif "ru_ref" in data["survey_metadata"]:
            key = BUSINESS_SURVEY_KEY
        else:
            raise ValueError(f"Missing qid or ru_ref in {feedback_file}")

        FEEDBACK_BY_SURVEY_TYPE[key].append((filename, data))

    except KeyError as ex:
        print(f"Warning: {filename} is missing required fields and will be skipped")
        print(ex)


def get_value_for_output_field_from_feedback(
    *, feedback: dict, output_field: OutputField
) -> str:
    survey_metadata = feedback["survey_metadata"]
    feedback_data = feedback["data"]
    keys = (
        [output_field.name] if isinstance(output_field.name, str) else output_field.name
    )

    value = None
    for key in keys:
        if key == "EMPTY_COLUMN":
            return ""

        if key in survey_metadata:
            value = survey_metadata.get(key)
        elif key in feedback_data:
            value = feedback_data.get(key)
        else:
            value = feedback.get(key)

        if value:
            if key == "feedback_text":
                value = (
                    value.replace("\n", " ")
                    .replace("\r", " ")
                    .replace('"', '""')
                    .strip()
                )

                value = f'"{value}"'

            break

    if not value and not output_field.default_value:
        raise KeyError(
            f"Could not find value for '{output_field.name}' in feedback and no default value was specified."
        )

    return value or output_field.default_value or "No value provided"


def write_to_csv(
    *, file: IO, earliest_submission_formatted: str, feedback: dict, filename: str
):
    """
    Write feedback data to a CSV file.
    """

    try:
        output_string = ",".join(
            get_value_for_output_field_from_feedback(
                feedback=feedback, output_field=output_field
            )
            for output_field in CONFIG.output_fields
        )
        # Write formatted feedback data to the CSV file
        file.write(f"{earliest_submission_formatted},{output_string},{filename}\n")

    except KeyError as ex:
        print(
            f"Warning: {filename} is missing required fields and will be skipped.{ENDC} - {RED_COLOUR}{ex}{ENDC}{YELLOW_COLOUR}"
        )

        return False

    return True


# Define the main function to aggregate and process feedback
def aggregate_feedback():
    """
    Aggregate feedback from a folder of feedback files, and write the aggregated feedback to a CSV file.
    """

    # Get all feedback files (JSON content) from the specified source folder
    feedback_files = glob.glob(f"{CONFIG.source_folder}/*")

    # Iterate through each feedback file and process its content
    for feedback_file in feedback_files:
        process_feedback_file(
            feedback_file=feedback_file,
        )

    # Exist if not feedback data found
    if (
        not FEEDBACK_BY_SURVEY_TYPE[BUSINESS_SURVEY_KEY]
        and not FEEDBACK_BY_SURVEY_TYPE[NON_BUSINESS_SURVEY_KEY]
    ):
        print(f"No valid feedback data found in {CONFIG.source_folder}. Exiting ...")
        sys.exit(1)

    for survey_type, feedback_data in FEEDBACK_BY_SURVEY_TYPE.items():
        if not feedback_data:
            print(f"No valid '{survey_type}' survey feedback data found. Skipping ...")
            continue

        sorted_feedback = sorted(
            feedback_data, key=lambda x: datetime.fromisoformat(x[1]["submitted_at"])
        )

        first_submission = datetime.fromisoformat(sorted_feedback[0][1]["submitted_at"])
        first_submission_formatted = first_submission.strftime("%b %d %Y")
        first_submission_yyyy_mm_dd = first_submission.strftime("%Y-%m-%d")  # type: ignore

        # Create a CSV file for storing aggregated feedback data
        output_filename = (
            f"- {CONFIG.aggregated_file_prefix}-{survey_type.title()}-"
            f"Surveys-{first_submission_yyyy_mm_dd}.csv"
        )

        passed = False
        # Write feedback data to the CSV file in the specified format
        with open(
            os.path.join(CONFIG.source_folder, output_filename), "w", encoding="utf-8"
        ) as file:
            for filename, feedback in sorted_feedback:
                passed += write_to_csv(
                    file=file,
                    earliest_submission_formatted=first_submission_formatted,
                    feedback=feedback,
                    filename=filename,
                )

        # Print a message indicating successful processing of feedback files
        print(
            f"{GREEN_COLOUR}Processed {passed}/{len(sorted_feedback)} '{survey_type}' "
            f"survey feedback files for {first_submission_yyyy_mm_dd}.{ENDC}"
        )


# Entry point of the script
if __name__ == "__main__":
    # Call the main function to process and aggregate feedback
    aggregate_feedback()
