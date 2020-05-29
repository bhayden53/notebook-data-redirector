import logging

import common


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def lambda_handler(event, context):
    ddb_table = common.get_ddb_table()
    box_client, _ = common.get_box_client()
    root_folder = box_client.folder(common.BOX_FOLDER_ID)

    LOGGER.info("Checking files in Box")
    shared_file_ids = set()
    shared_filepaths = set()
    count = 0
    for file, shared in common.iterate_files(root_folder):
        count += 1
        if (not common.is_box_file_public(file)) and (common.is_any_parent_public(box_client, file)):
            # this includes an api call
            file = common.create_shared_link(box_client, file, access=u"open", allow_download=True)
        if common.is_box_file_public(file):
            shared_file_ids.add(file.id)
            shared_filepaths.add(common.get_filepath(file))
            common.put_file_item(ddb_table, file)
        else:
            common.delete_file_item(ddb_table, file)
    LOGGER.info("Processed %s files", count)

    LOGGER.info("Checking items in DynamoDB")
    count = 0
    scan_response = ddb_table.scan()
    delete_keys = set()
    while True:
        for item in scan_response["Items"]:
            count += 1
            if (item["box_file_id"] not in shared_file_ids) or (item["filepath"] not in shared_filepaths):
                delete_keys.add(item["filepath"])

        # If the data returned by a scan would exceed 1MB, DynamoDB will begin paging.
        # The LastEvaluatedKey field is the placeholder used to request the next page.
        if scan_response.get("LastEvaluatedKey"):
            scan_response = ddb_table.scan(ExclusiveStartKey=scan_response["LastEvaluatedKey"])
        else:
            break

    for key in delete_keys:
        ddb_table.delete_item(Key={"filepath": key})
    LOGGER.info("Processed %s items", count)
