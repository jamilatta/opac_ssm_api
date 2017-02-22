# coding: utf-8
import os
import six
import grpc
import json
import logging
from imp import reload

logger = logging.getLogger(__name__)

from opac_ssm_api import utils

HOST_NAME = os.getenv('OPAC_SSM_GRPC_SERVER_HOST', 'localhost')
HOST_PORT = os.getenv('OPAC_SSM_GRPC_SERVER_PORT', '5000')
HTTP_PROTO_PORT = os.getenv('OPAC_SSM_PORT', '8001')
PROTO_PATH = os.getenv('OPAC_SSM_PROTO_FILE_PATH', '/static/proto/opac.proto')

try:
    import opac_pb2
except ImportError:
    logger.warning("Retrieving proto file from URL: %s:%s%s", HOST_NAME, HTTP_PROTO_PORT, PROTO_PATH)
    utils.generate_pb_files(HOST_NAME, HTTP_PROTO_PORT, PROTO_PATH)
    import opac_pb2


class Client(object):

    def __init__(self, host=HOST_NAME, port=HOST_PORT, proto_http_port=HTTP_PROTO_PORT,
                 proto_path=PROTO_PATH, update_pb_class=False):
        """
        Initialize channel and stub objects.

        Params:
            :param: host: string, default='localhost'
            :param: port: string, default='5000' (default of the SSM server service)
        """

        if update_pb_class:
            utils.generate_pb_files(HOST_NAME, HTTP_PROTO_PORT, PROTO_PATH)
            reload(opac_pb2)

        self.channel = grpc.insecure_channel('{0}:{1}'.format(host, port))
        self.stubAsset = opac_pb2.AssetServiceStub(self.channel)
        self.stubBucket = opac_pb2.BucketServiceStub(self.channel)

    def add_asset(self, pfile, filename='', filetype='', metadata='',
                  bucket_name='UNKNOW'):
        """
        Add asset to SSM.

        Params:
            :param pfile: pfile path (Mandatory) or a file pointer
            :param filetype: string
            :param metadata: dict
            :param filename: filename is mandatory if pfile is a file pointer
            :param bucket_name: name of bucket

        Return id of the asset, string of (UUID4)

        Raise ValueError if param metadata is not a dict
        Raise ValueError if not set filename when pfile is a file pointer
        Raise IOError if pfile is not a file or cant read the file
        """
        if not metadata:
            metadata = {}
        elif not isinstance(metadata, dict):
            error_msg = 'Param "metadata" must be a Dict or None.'
            logger.error(error_msg)
            raise ValueError(error_msg)

        if hasattr(pfile, 'read'):
            if not filename:
                error_msg = 'Param "filename" is required'
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                filename = filename
                file_content = pfile.read()
        else:
            if os.path.isfile(pfile) and os.access(pfile, os.R_OK):
                with open(pfile, 'rb') as fp:
                    filename = os.path.basename(getattr(fp, 'name', None))
                    file_content = fp.read()
            else:
                error_msg = "The file pointed: (%s) is not a file or is unreadable."
                logger.error(error_msg, pfile)
                raise IOError(error_msg)

        asset = opac_pb2.Asset(
            file=file_content,
            filename=filename,
            type=filetype,
            metadata=json.dumps(metadata),
            bucket=bucket_name
        )

        return self.stubAsset.add_asset(asset).id

    def get_asset(self, id):
        """
        Get asset by id.

        Params:
            :param id: string id of the asset (Mandatory)

        Return dict with asset params

        Raise ValueError if param id is not a str|unicode
        """

        if not isinstance(id, six.string_types):
            msg = 'Param id must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        asset = self.stubAsset.get_asset(opac_pb2.TaskId(id=id))

        return {
            'file': asset.file,
            'filename': asset.filename,
            'type': asset.type,
            'metadata': asset.metadata,
            'uuid': asset.uuid,
            'bucket': asset.bucket
        }

    def get_asset_info(self, id):
        """
        Get asset info by id.

        Params:
            :param id: string id of the asset (Mandatory)

        Raise ValueError if param id is not a str|unicode
        """

        if not isinstance(id, six.string_types):
            msg = 'Param id must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        asset_info = self.stubAsset.get_asset_info(opac_pb2.TaskId(id=id))

        return {
            'url': asset_info.url,
            'url_path': asset_info.url_path
        }

    def get_task_state(self, id):
        """
        Get task state by id

        Params:
            :param id: string id of the task (Mandatory)

        Raise ValueError if param id is not a str|unicode
        """

        if not isinstance(id, six.string_types):
            msg = 'Param id must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        task_state = self.stubAsset.get_task_state(opac_pb2.TaskId(id=id))

        return task_state.state

    def update_asset(self, uuid, pfile=None, filename=None, filetype=None, metadata=None,
                    bucket_name=None):
        """
        Update asset to SSM.

        Params:
            :param uuid: uuid to update
            :param pfile: pfile path (Mandatory) or a file pointer
            :param filetype: string
            :param metadata: dict
            :param filename: filename is mandatory if pfile is a file pointer
            :param bucket_name: name of bucket

        Return id of the asset, string of (UUID4)

        Raise ValueError if param uuid is not a str|unicode
        """

        if not isinstance(uuid, six.string_types):
            raise ValueError('Param "uuid" must be a str|unicode.')

        update_params = {}

        if self.stubAsset.exists_asset(opac_pb2.TaskId(id=uuid)):

            if not metadata:
                update_params['metadata'] = {}
            elif not isinstance(metadata, dict):
                error_msg = 'Param "metadata" must be a Dict or None.'
                logger.exception(error_msg)
                raise ValueError(error_msg)
            else:
                update_params['metadata'] = json.dumps(metadata)

            if pfile is not None:
                if hasattr(pfile, 'read'):
                    if not filename:
                        error_msg = 'Param "filename" is required'
                        logger.exception(error_msg)
                        raise IOError(error_msg)
                    else:
                        filename = filename
                        file_content = pfile.read()
                else:
                    if os.path.isfile(pfile) and os.access(pfile, os.R_OK):
                        with open(pfile, 'rb') as fp:
                            filename = os.path.basename(getattr(fp, 'name', None))
                            file_content = fp.read()
                    else:
                        error_msg = "The file pointed: (%s) is not a file or is unreadable."
                        logger.error(error_msg, pfile)
                        raise IOError(error_msg)

                update_params['file'] = file_content
                update_params['filename'] = filename

            if filetype:
                update_params['type'] = filetype

            if bucket_name:
                update_params['bucket'] = bucket_name

            asset = opac_pb2.Asset(**update_params)

            return self.stubAsset.update_asset(asset).id
        else:
            error_msg = "Dont exist asset with id: %s"
            logger.error(error_msg, uuid)

    def remove_asset(self, id):
        """
        Task to remove asset by id.

        Params:
            :param id: UUID (Mandatory)

        Raise ValueError if param id is not a str|unicode
        """

        if not isinstance(id, six.string_types):
            raise ValueError('Param "id" must be a str|unicode.')

        if self.stubAsset.exists_asset(opac_pb2.TaskId(id=id)):
            return self.stubAsset.remove_asset(opac_pb2.TaskId(id=id))

    def add_bucket(self, name):
        """
        Add bucket.

        Params:
            :param name: name (Mandatory).

        Return id of the bucket, string of (UUID4)

        Raise ValueError if param name is not a str|unicode
        """

        if not isinstance(name, six.string_types):
            msg = 'Param name must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        return self.stubBucket.add_bucket(opac_pb2.BucketName(name=name)).id

    def update_bucket(self, name, new_name):
        """
        Update bucket.

        Params:
            :param name: name (Mandatory).
            :param new_name: new_name (Mandatory).

        Return id of the bucket, string of (UUID4)

        Raise ValueError if param name or new_name is not a str|unicode
        """

        if not isinstance(name, six.string_types):
            msg = 'Param name must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        if not isinstance(new_name, six.string_types):
            msg = 'Param new_name must be a str|unicode.'
            logger.exception(msg)
            raise ValueError(msg)

        return self.stubBucket.add_update(
                    opac_pb2.BucketName(name=name, new_name=new_name)).id

    def remove_bucket(self, name):
        """
        Task to remove bucket by name.

        Params:
            :param name: String (Mandatory)

        Raise ValueError if param name is not a str|unicode
        """

        if not isinstance(name, six.string_types):
            raise ValueError('Param "name" must be a str|unicode.')

        if self.stubBucket.exists_bucket(opac_pb2.BucketName(name=name)):
            return self.stubBucket.remove_bucket(opac_pb2.BucketName(name=name))

