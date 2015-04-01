import cmislib
import StringIO
from django.core.files.storage import Storage
from django.core.files import File
from django.core.urlresolvers import reverse
from django.conf import settings

from initat.core.alfresco import logger
from initat.core.alfresco.alfresco import get_uuid, alfresco_handler
from initat.core.models import AlfrescoDocument


class AlfrescoStorageError(Exception):
    pass


class AlfrescoStorage(Storage):
    def __init__(self, directory=None):
        super(AlfrescoStorage, self).__init__()
        if directory is None:
            directory = settings.DEFAULT_ALFRESCO_DIR
        self.handler = alfresco_handler(log_com=lambda x, y: logger.info(x),
                                        directory=directory)

    def __del__(self):
        self.handler.close()

    def _open(self, name, mode="rb"):
        document = self.handler.load_content(uuid=name)
        sio = StringIO.StringIO(document.getContentStream().read())
        return File(sio, mode)

    # FIXME the handler should return a UUID to indicate success
    def _save(self, name, content):
        success = self.handler.store_content(name, content.read(), check_for_existing=True,
                                             create_new_version_if_exists=True)
        uuid = None
        if not success:
            logger.error("Upload of %s failed!" % name)
            raise AlfrescoStorageError("Storing failed: %s" % name)
        else:
            logger.info("Upload of %s successful!" % name)
            document = self.handler.load_content(path=name)
            version_major, version_minor = document.getProperties()["cmis:versionLabel"].split(".")
            uuid = get_uuid(document)
            # Create or update db entry
            AlfrescoDocument(uuid=uuid, version_major=version_major,
                             path=name, version_minor=version_minor).save()
        return uuid

    def get_valid_name(self, name):
        # The alfresco_tools do valid name checking.
        return name

    def get_available_name(self, name):
        # Alfresco does the versioning for us.
        return name

    def path(self, name):
        raise NotImplementedError("This backend doesn't support absolute paths")

    def delete(self, name):
        pass

    def exists(self, name):
        print "* exists", name

    def listdir(self, path):
        directories = []
        files = []
        for element in list(self.handler.get_dir_list(path)):
            if isinstance(element, cmislib.model.Folder):
                directories.append(element.name)
            elif isinstance(element, cmislib.model.Document):
                files.append(element.name)
        return directories, files

    def url(self, name):
        return reverse("get_alfresco_file", kwargs={"uuid": name})

    def size(self, name):
        # cmis:contentStreamLength
        pass

    def modified_time(self, name):
        # cmis:lastModificationDate
        pass

    def created_time(self, name):
        # cmis:creationDate
        pass

    def accessed_time(self, name):
        # No good property
        pass
