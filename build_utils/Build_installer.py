import yaml
import os
import sys
import logging
from shutil import copyfile, rmtree
from distutils.spawn import find_executable
logging.basicConfig(format='%(levelname)7s %(message)s', level=10)

try:
    # for python 2
    input = raw_input
except NameError:
    # for python 3
    basestring = (str, bytes)


# def copy_files(source, destination, )

class Builder():
    supported_tags = ['name', 'version', 'include_data', 'exclude_data', 'remap_folders', 'ArcGIS_support', 'QGIS_support', 'build_folder', 'Python_version', 'installer_script', 'splash_screen']
    runtime_dir = False
    root_dir = False
    target_dir = False
    build_dir = False

    def __init__(self):

        if find_executable('7z.exe') is None:
            raise RuntimeError('Could not find the 7zip executable. Please install 7zip before trying again, or add it to your PATH if already installed')

        self.read_options()

        logging.info(' Begin to build {0} version {1}'.format(self.options['name'], self.options['version']))

        # moving to the right directory
        self.runtime_dir = os.getcwd()
        self.root_dir = os.path.dirname(os.path.dirname(self.runtime_dir))
        logging.info('  Moving to {0}'.format(self.root_dir))
        os.chdir(self.root_dir)

        # sort out build folders
        if 'build_folder' in self.options.keys() and self.options['build_folder'] is not None:
            self.build_dir = os.path.join(self.root_dir, self.options['build_dir'])
        else:
            self.build_dir = os.path.join(self.runtime_dir, 'Build')
        logging.info('  Build folder: {0}'.format(self.build_dir))
        if os.path.isdir(self.build_dir):
            rmtree(self.build_dir)
        self.target_dir = os.path.join(self.build_dir, 'xGIS{0}{1}'.format(os.sep, self.options['name']))
        logging.info('  Target folder: {0}'.format(self.target_dir))
        os.makedirs(self.target_dir)

        # prepare config file and check for build configs
        self.make_config()

        # find and copy files based on inclusion, exclusion and remapping rules
        include = self.options['include_data']
        exclude = self.options['exclude_data']
        remap = self.options['remap_folders']
        self.finder('', include, exclude, remap)
        logging.info('  All files are ready for build')

    def build(self):
        logging.info('  Compressing the folder {0}'.format(self.target_dir))
        os.chdir(self.build_dir)
        if os.path.isfile('Installer.7z'):
            os.remove('Installer.7z')
        os.system('7z.exe a -t7z {0} {1}'.format('Installer.7z', 'xGIS'))

        logging.info(' Building the installer')
        copyfile(os.path.join(self.runtime_dir, '7zsd_All_x64.sfx'), os.path.join(self.build_dir, '7zsd_All_x64.sfx'))
        installer_filename = '{0}_v{1}.exe'.format(self.options['name'], self.options['version'])
        # installer_path = os.path.join(self.build_dir, installer_filename)
        if os.path.isfile(installer_filename):
            os.remove(installer_filename)
        os.system('COPY /b 7zsd_All_x64.sfx + config.txt + Installer.7z {0}'.format(installer_filename))
        return installer_filename


    def read_options(self):
        # load the config file
        if os.path.isfile('build_config.yaml'):
            logging.info('  Reading options from {0}'.format(os.path.abspath('build_config.yaml')))
            self.options = yaml.load(open('build_config.yaml'), Loader=yaml.FullLoader)
        else:
            raise IOError('The build_config.yaml file is missing')

        # check for invalid tags
        for k in self.options.keys():
            if k not in self.supported_tags:
                raise RuntimeError("The tag '{0}' is not supported".format(k))


    def make_config(self):
        # open template (this can be changed if you need)
        with open(os.path.join(self.runtime_dir, 'config_template.txt')) as template:
            config_text = template.read()

        # check for ArcGIS support
        if self.options['ArcGIS_support']:
            arcgis = 1
        else:
            arcgis = 0

        # check for QGIS support
        if self.options['QGIS_support']:
            qgis = 1
        else:
            qgis = 0

        # check for wrong settings
        if arcgis + qgis == 0:
            raise RuntimeError("You need to select at least one of 'ArcGIS_support' or 'QGIS_support'")
        if self.options['Python_version'] == 3 and arcgis == 1:
            raise NotImplementedError("Currently there is no support for ArcGIS and Python 3")

        # check for installer script and copy it
        if self.options['installer_script']:
            installer_script = self.options['installer_script']
            for path in [self.root_dir, self.runtime_dir]:
                installer = os.path.join(path, installer_script)
                if os.path.isfile(installer):
                    break
            else:
                raise IOError("Could not find the installer script: {0}. Make sure to place it in the toolbox directory".format(installer_script))
            copyfile(installer, os.path.join(self.target_dir, installer_script))
            installer_script = 'xGIS\\\\{0}\\\\{1}'.format(self.options['name'], installer_script)
        else:
            installer_script = ''

        # create the config.txt
        logging.info('  Writing config file in {0}'.format(os.path.join(self.build_dir, 'config.txt')))
        with open(os.path.join(self.build_dir, 'config.txt'), 'w') as config:
            config.write(
                config_text.format(
                    name=self.options['name'],
                    arcgis=arcgis,
                    qgis=qgis,
                    version=str(self.options['version']),
                    python=str(self.options['Python_version']),
                    installer=installer_script,
                    splash=self.options['splash_screen']
                )
            )


    def finder(self, init_subpath, include, exclude, remap):
        for k in include.keys():
            # get current level of info
            sub_include = include[k]
            try:
                sub_exclude = exclude[k]
            except (KeyError, TypeError):
                sub_exclude = False
            try:
                sub_remap = remap[k]
            except (KeyError, TypeError):
                sub_remap = False

            # find the source path
            current_subpath = os.path.join(init_subpath, k)

            source_path = os.path.join(self.root_dir, current_subpath)
            if not os.path.isdir(source_path):
                raise IOError("Could not find the path '{0}'".format(source_path))

            if isinstance(sub_remap, basestring):
                dest_path = os.path.join(self.target_dir, sub_remap)
            else:
                dest_path = os.path.join(self.target_dir, current_subpath)
            if not os.path.isdir(dest_path):
                os.makedirs(dest_path)

            logging.info('looking into {0}'.format(source_path))
            logging.info('The content should be copied to {0}'.format(dest_path))

            # if the content is still a dictionary, go deeper
            if isinstance(sub_include, dict):
                self.finder(current_subpath, sub_include, sub_exclude, sub_remap)
            # if the content is a list, we already have the list of files to copy
            elif isinstance(sub_include, list):
                self.copier(sub_include, source_path, dest_path)
            elif sub_include is None:
                files = self.list_files(k)
                if isinstance(sub_exclude, list):
                    files = [f for f in files if f not in sub_exclude]
                elif sub_exclude is False:
                    pass
                else:
                    raise TypeError('{0} is not a valid file exclusion list'.format(sub_exclude))
                self.copier(files, source_path, dest_path)
            else:
                raise TypeError("Could not process the folder '{0}'. Please specify files to include as lists (using -)".format(k) )


    @staticmethod
    def copier(files, source_dir, target_dir):
        for f in files:
            source = os.path.join(source_dir, f)
            destination = os.path.join(target_dir, f)
            if os.path.isfile(source):
                logging.info('copying {0} to {1}'.format(source, destination))
                copyfile(source, destination)
            else:
                raise IOError("Could not find file'{0}' in folder '{1}'".folder(f, source_dir))


    @staticmethod
    def list_files(path):
        for f in os.listdir(path):
            if os.path.isfile(os.path.join(path, f)):
                yield f


if __name__ == "__main__":
    try:
        run = Builder()
        out = run.build()
        logging.info('Building succeeded: {0}'.format(out))
    except Exception as e:
        logging.exception('Building failed!')
    answer = input("  INPUT Press Enter to continue...")
