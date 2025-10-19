import os
import time
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import humanize  # For human-readable time differences and sizes
from rich.console import Console
from rich.table import Table
import math
import A_GIS

def format_size(size_in_bytes):
    """Convert size in bytes to human-readable format."""
    return humanize.naturalsize(size_in_bytes, binary=True, format='%.2f')

def format_time_since(timestamp):
    """Calculate time since the given timestamp."""
    time_diff = datetime.now() - datetime.fromtimestamp(timestamp)
    return humanize.naturaltime(time_diff)

def filter_row(current_angle,last_change_in_angle,last_mod_time,size_in_bytes):
    dt = (datetime.now() - datetime.fromtimestamp(last_mod_time)).total_seconds()
    if math.fabs(current_angle)<float(os.getenv('AGENT_FM_MIN_ANGLE',0.0)):
        return True
    elif math.fabs(last_change_in_angle)<float(os.getenv('AGENT_FM_MIN_ANGLE_CHANGE',0.0)):
        return True
    elif dt > float(os.getenv('AGENT_FM_MAX_AGE', 86400)):
        return True
    elif size_in_bytes < float(os.getenv('AGENT_FM_MIN_BYTES',10)):
        return True
    else:
        return False

def main():
    # Initialize rich console
    console = Console()

    # Connect to MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['file_monitor']  # Replace with your database name
    collection = db['file_changes']  # Replace with your collection name

    while True:
        # Prune any missing/deleted documents.
        A_GIS.File.Database.prune_deleted(collection=collection,sha256=None)

        # Find all documents
        cursor = list(collection.find())

        # Sort documents based on the last modification time in 'mod_time_list'
        cursor.sort(key=lambda doc: doc['mod_time_list'][-1] if 'mod_time_list' in doc and doc['mod_time_list'] else 0, reverse=False)

        # Create a Rich table
        table = Table(show_header=True)
        table.add_column("Filename", style="dim", header_style="dim")  # Removed width constraint for full path
        table.add_column("Size", justify="right", style="yellow", header_style="yellow")  # Size in yellow
        table.add_column("Modified", justify="right", style="bold white", header_style="bold white")  # Modified Time in bold white
        table.add_column("Angle", justify="right", style="bold blue", header_style="blue")  # Angle in blue
        table.add_column("Delta Angle", justify="right", style="bold green", header_style="green")  # Last Change in Angle in green

        for doc in cursor:
            file_path = doc['_id']  # Assuming '_id' is the file path

            if os.path.exists(file_path):

                # Get size from the filesystem
                size_in_bytes = os.path.getsize(file_path)
                size = format_size(size_in_bytes)

                # Get modified time (since)
                mod_time_list = doc.get('mod_time_list', [])
                if mod_time_list:
                    last_mod_time = mod_time_list[-1]
                    time_since_mod = format_time_since(last_mod_time)
                else:
                    time_since_mod = 'N/A'

                # Get angle
                angle_list = doc.get('angle_list', [])
                if angle_list:
                    current_angle = float(angle_list[-1])
                    # Calculate last change in angle
                    if len(angle_list) >= 2:
                        last_change_in_angle = current_angle - float(angle_list[-2])
                    else:
                        last_change_in_angle = 0
                else:
                    current_angle = 0
                    last_change_in_angle = 0

                # Format angles with two decimal places
                if filter_row(current_angle, last_change_in_angle, last_mod_time, size_in_bytes):
                    continue
                current_angle_formatted = f"{current_angle:.2f}" if current_angle is not None else 'N/A'
                last_change_in_angle_formatted = f"{last_change_in_angle:.2f}" if last_change_in_angle is not None else 'N/A'

                # Add row to the table
                table.add_row(
                    file_path,
                    size,
                    time_since_mod,
                    current_angle_formatted,
                    last_change_in_angle_formatted
                )

        # Clear the console (optional)
        console.clear()

        # Display the table
        console.print(table)

        # Wait for 30 seconds before the next iteration
        time.sleep(30)

if __name__ == '__main__':
    main()
