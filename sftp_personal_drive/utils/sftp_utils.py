import paramiko

def get_sftp_connection(host, username, password):
    transport = paramiko.Transport((host, 22))
    transport.connect(username=username, password=password)
    return paramiko.SFTPClient.from_transport(transport), transport


def list_files(sftp, username):
    remote_path = f"/home/{username}/uploads"
    try:
        return sftp.listdir(remote_path)
    except FileNotFoundError:
        sftp.mkdir(remote_path)
        return []
