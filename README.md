# Introduction
This repository provides a script to upload an archive with multiple parts to Amazon Web Services (AWS) Glacier. The AWS Glacier is a low-cost storage service that provides secure and durable storage for data archiving and backup. This script can be used to archive large files, such as video files, audio files, or databases, to the Glacier service.

# Usage
To use the script, follow these steps:

1) Copy the main.py file to the directory where your archive.zip file lives. 

2) Install AWS CLI and run aws configure to configure your AWS credentials. You can preconfigure your AWS region as well. You also need to create a vault in the AWS Glacier to archive your files.

3) Run the code using the following command in the terminal:

python main.py [Archive Filename] [Archive Description] [Vaultname]

For example, to upload an archive file named myfiles.zip with a description of Myfiles to a vault named my-vault, run the following command:

python main.py myfiles.zip Myfiles my-vault

The script will split the archive file into multiple parts, upload the parts to the Glacier service, and then combine them into a single archive.


# Notes

Script uses chunk size of 4Gb by default. You can change this based on your requirement.

