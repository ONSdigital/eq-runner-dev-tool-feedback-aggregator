import argparse
import glob
import json
import os
import sys
from datetime import datetime


# Define the main function to aggregate and process feedback
def aggregate_feedback(source_folder):
    """Aggregate feedback from a folder of feedback files, and write the aggregated feedback to a CSV file."""

    # Get all feedback files (JSON content) from the specified source folder
    feedback_files = glob.glob(f"{source_folder}/*")

    # Initialize variables to store feedback data and earliest date
    earliest_date = None
    feedback_data = []

    # Iterate through each feedback file and process its content
    for feedback_file in feedback_files:
        filename = os.path.basename(feedback_file)

        # Skip files with aggregated feedback in the filename
        if "aggregated-feedback" in filename.lower():
            continue

        # Read and process valid JSON feedback data
        with open(feedback_file, "r", encoding="utf-8") as file:
            try:
                feedback_data.append((filename, json.load(file)))
            except json.decoder.JSONDecodeError:
                print(f"Warning: {feedback_file} is not valid JSON and will be skipped")

        # Extract the date from the filename and determine the earliest date
        date_part = filename.split("fb-")[-1].split("-")
        date = datetime.strptime("-".join(date_part), "%H-%M-%S_%d-%m-%Y")
        if earliest_date is None or date < earliest_date:
            earliest_date = date

    if not feedback_files:
        print(f"No feedback files found in {source_folder}")
        sys.exit(1)

    earliest_date_formatted = earliest_date.strftime("%b %d %Y")

    # Create a CSV file for storing aggregated feedback data
    output_filename = f"1. Aggregated-Feedback-{earliest_date.strftime('%Y-%m-%d')}.csv"

    # Write feedback data to the CSV file in the specified format
    with open(
        os.path.join(source_folder, output_filename), "w", encoding="utf-8"
    ) as file:
        for filename, feedback in feedback_data:
            survey_metadata = feedback["survey_metadata"]
            safe_feedback = (
                feedback["data"]["feedback_text"]
                .replace("\n", " ")
                .replace("\r", " ")
                .replace('"', '""')
                .strip()
            )
            top_level_id = survey_metadata.get("ru_ref") or survey_metadata.get("qid")
            period_id = survey_metadata.get("period_id") or "Unknown Period ID"
            form_type = survey_metadata.get("form_type") or "Unknown Form Type"

            file.write(
                f'{earliest_date_formatted},{period_id},"{safe_feedback}",'
                f'{feedback["data"]["feedback_type"]},,{form_type},{top_level_id},'
                f'{feedback["submitted_at"]},{survey_metadata["survey_id"]},{filename}\n'
            )

    # Print a message indicating successful processing of feedback files
    print(
        f"Processed {len(feedback_data)} feedback files for {earliest_date_formatted}"
    )


# Entry point of the script
if __name__ == "__main__":
    # Create a CLI with an optional source folder argument
    parser = argparse.ArgumentParser(
        description="Aggregate feedback from a folder of feedback files"
    )
    parser.add_argument(
        "--source", default="feedback_data", help="Folder containing feedback files"
    )
    args = parser.parse_args()

    # Check if the specified source folder exists
    if not os.path.exists(args.source):
        print(f"The specified source folder '{args.source}' does not exist.")
        sys.exit(1)

    # Call the main function to process and aggregate feedback
    aggregate_feedback(args.source)
