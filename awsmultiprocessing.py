import sys
import os
import subprocess
import json
import hashlib
import math
import shutil
import time
from multiprocessing import Pool, cpu_count

def convert_to_bytes(size_str):
    size_str = size_str.lower()
    if size_str.endswith('g'):
        return int(size_str[:-1]) * 1024 ** 3
    elif size_str.endswith('m'):
        return int(size_str[:-1]) * 1024 ** 2
    elif size_str.endswith('k'):
        return int(size_str[:-1]) * 1024
    else:
        return int(size_str)
    
def sha256_hash(data):
    sha256 = hashlib.sha256()
    sha256.update(data)
    return sha256.digest()


def glacier_tree_hash(chunks_hashes):
    while len(chunks_hashes) > 1:
        new_chunks_hashes = []

        for i in range(0, len(chunks_hashes), 2):
            if i + 1 < len(chunks_hashes):
                combined_hash = sha256_hash(
                    chunks_hashes[i] + chunks_hashes[i + 1])
                new_chunks_hashes.append(combined_hash)
            else:
                new_chunks_hashes.append(chunks_hashes[i])

        chunks_hashes = new_chunks_hashes

    return chunks_hashes[0]


def main(file_path):
    try:
        with open(file_path, "r") as file:
            filename = file.name
            print(f"File name: {filename}")
    except FileNotFoundError:
        print(f"Error: file '{file_path}' not found")
        sys.exit(1)


def size(file_path):
    try:
        file_size = os.path.getsize(file_path)
        print(f"File size: {file_size} bytes")
    except FileNotFoundError:
        print(f"Error: file '{file_path}' not found")
        sys.exit(1)


def upload_part(params):
    i, file_name, set_low_value, set_high_value, total_size, upload_id, vaultname, directory_path = params

    print(
        f"Processing: {file_name}. Bytes: {set_low_value}-{set_high_value}/{total_size}")
    print(f"UploadId: {upload_id}. Vault: {vaultname}")

    cmd = [
        'aws',
        'glacier',
        'upload-multipart-part',
        '--upload-id',
        upload_id,
        '--body',
        os.path.join(directory_path, file_name),
        '--range',
        f'bytes {set_low_value}-{set_high_value}/{total_size}',
        '--account-id',
        '-',
        '--vault-name',
        vaultname
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        print(f"Error running command: {result.stderr}")
        exit(1)

    # Parse the output as JSON
    json_output = json.loads(result.stdout)
    return json_output

def processchunks(file_path, description, vaultname, sizeofchunk):
    file_name_prefix = os.path.basename(file_path)
    name, extension = os.path.splitext(file_name_prefix)
    temp_dir = name+'_temp'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        os.mkdir(os.path.join(script_dir, temp_dir))
    except:
        print(f"make dir didnt work")
    cmd = ["split", "-b", str(sizeofchunk), "--verbose",
           file_path, os.path.join(temp_dir, "chunk")]

    subprocess.run(cmd, check=True)
    directory_path = os.path.join(script_dir, temp_dir)
    files = os.listdir(directory_path)
    sorted_files = sorted(files)

    cmd = [
        'aws',
        'glacier',
        'initiate-multipart-upload',
        '--account-id', '-',
        '--archive-description', description,
        '--part-size', str(sizeofchunk),
        '--vault-name', vaultname
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running command: {result.stderr}")
        exit(1)

    json_output = json.loads(result.stdout)
    upload_id = json_output['uploadId']
    print(f"Task UploadId: {upload_id}")

    set_low_value = 0
    total_size = os.path.getsize(file_path)
    tasks = []

    for i, file_name in enumerate(sorted_files, start=1):
        file_size = os.path.getsize(os.path.join(directory_path, file_name))
        set_high_value = min(set_low_value + sizeofchunk - 1, total_size - 1)

        tasks.append((i, file_name, set_low_value, set_high_value,
                     total_size, upload_id, vaultname, directory_path))

        set_low_value = set_high_value + 1

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(upload_part, tasks)

    print("Verifying checksum...")
    chunk_files = []
    chunk_size = 1024 * 1024
    for file in sorted_files:
        chunk_files.append(os.path.join(directory_path, file))

    chunk_hashes = []

    for i, chunk_file in enumerate(chunk_files, start=1):
        with open(chunk_file, 'rb') as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                chunk_hash = sha256_hash(data)
                chunk_hashes.append(chunk_hash)
        print(f"Processed checksum of chunk file {i}/{len(chunk_files)}...")

    tree_hash = glacier_tree_hash(chunk_hashes)
    tree_hash_hex = tree_hash.hex()

    print(f'Glacier tree hash: {tree_hash_hex}')

    finalcmd = [
        'aws',
        'glacier',
        'complete-multipart-upload',
        '--checksum',
        tree_hash_hex,
        '--archive-size',
        str(total_size),
        '--upload-id',
        upload_id,
        '--account-id',
        '-',
        '--vault-name',
        vaultname
    ]
    result = subprocess.run(finalcmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running command: {result.stderr}")
        exit(1)

    json_output = json.loads(result.stdout)
    print(json_output)

    print("Clean up...")
    shutil.rmtree(directory_path)
    print("Done")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Please specify a file path, description, vault name, and chunk size as arguments")
        sys.exit(1)

    file_path = sys.argv[1]
    description = sys.argv[2]
    vaultname = sys.argv[3]
    sizeofchunk = convert_to_bytes(sys.argv[4])
    main(file_path)
    size(file_path)
    processchunks(file_path, description, vaultname, sizeofchunk)
