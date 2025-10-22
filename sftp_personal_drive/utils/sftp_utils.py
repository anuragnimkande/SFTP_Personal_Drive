import paramiko

def get_sftp_connection(host, username, password):
    transport = paramiko.Transport((host, 22))
    transport.connect(username=username, password=password)
    return paramiko.SFTPClient.from_transport(transport), transport


def list_files(sftp, username):
    remote_dir = f"/home/{username}/uploads"
    try:
        sftp.chdir(remote_dir)
    except IOError:
        return []
    return sftp.listdir()

