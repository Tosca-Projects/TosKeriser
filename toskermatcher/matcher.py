import ruamel.yaml
import requests
import re
import shutil
import os
import zipfile
import logging
import traceback
from sys import argv
from os import path
from six import print_
from . import __version__
from toscaparser.tosca_template import ToscaTemplate
from toscaparser.prereq.csar import CSAR
from toscaparser.common.exception import ValidationError

# DOCKERFINDER_URL = 'http://131.114.2.77/search'
# DOCKERFINDER_URL = 'http://127.0.0.1:3000/search'
DOCKERFINDER_URL = 'http://black.di.unipi.it:3000'
SEARCH_ENDPOINT = '/search'

CONTAINER_TYPE = 'tosker.nodes.Container'
IMAGE_TYPE = 'tosker.artifacts.Image'
DOCKERFILE_TYPE = 'tosker.artifacts.Dockerfile'

PROPERTY_SW = 'installed_sw'
PROPERTY_OS = 'os_distribution'

POLICY_TOP = 'top'
POLICY_SIZE = 'size'

_log = None


def _is_abstract(node):
    if node.type == 'tosker.nodes.Container':
        # if the container has the metaporperties
        if 'properties' in node.entity_tpl and\
            (PROPERTY_OS in node.entity_tpl['properties'] or
             PROPERTY_SW in node.entity_tpl['properties']):
            return True
        else:
            # if the container do not has the artifacts
            if 'artifacts' not in node.entity_tpl:
                return True
            else:
                # if the container has an artifacts of type image
                # but do not has the file
                _, value = list(node.entity_tpl['artifacts'].items())[0]
                _log.debug('artifacts {}'.format(value))
                if 'type' in value and\
                   IMAGE_TYPE == value['type'] and\
                   ('file' not in value or value['file'] is None):
                    return True
    return False


def _build_query(properties, policy=None, constraints={}):
    policy = POLICY_TOP if policy is None else policy
    errors = []

    def parse_unit(s):
        # bytes -> bytes
        # kB    -> kilo bytes
        # MB    -> mega bytes
        # GB    -> giga bytes
        s = s.lower()
        if s.endswith('bytes'):
            return int(s[:-5])
        elif s.endswith('kb'):
            return int(s[:-2]) * 1000
        elif s.endswith('mb'):
            return int(s[:-2]) * 1000 * 1000
        elif s.endswith('gb'):
            return int(s[:-2]) * 1000 * 1000 * 1000
        else:
            raise Exception('in parsing {}: unit not recognise'.format(s))

    def parse_op(s):
        if s.startswith('>='):
            return 'gte', s[2:]
        elif s.startswith('>'):
            return 'gt', s[1:]
        elif s.startswith('<='):
            return 'lte', s[2:]
        elif s.startswith('<'):
            return 'lt', s[1:]
        else:
            raise Exception('In parsing {}: operator not recognise'.format(s))

    def parse_unit_limit(s):
        s = s.strip()
        op, rest = parse_op(s)
        num = parse_unit(rest)
        return op, num

    def parse_limit(s):
        s = s.strip()
        op, rest = parse_op(s)
        return op, int(rest)

    query = {}
    if POLICY_TOP == policy:
        query['sort'] = ('stars', '-size', 'pulls')
    if POLICY_SIZE == policy:
        query['sort'] = ('-size', 'stars', 'pulls')

    if PROPERTY_SW in properties:
        for k, v in properties[PROPERTY_SW].items():
            query[k.lower()] = v
    if PROPERTY_OS in properties:
        # TODO: implement distribution query
        pass
    if 'size' in constraints:
        try:
            _log.debug('size {}'.format(constraints['size']))
            op, num = parse_unit_limit(constraints['size'])
            query['size_{}'.format(op)] = num
        except Exception as e:
            errors.append(e.args[0])
    if 'pulls' in constraints:
        try:
            op, num = parse_limit(constraints['pulls'])
            query['pulls_{}'.format(op)] = num
        except Exception as e:
            errors.append(e.args[0])
    if 'stars' in constraints:
        try:
            op, num = parse_limit(constraints['stars'])
            query['stars_{}'.format(op)] = num
        except Exception as e:
            errors.append(e.args[0])

    if len(errors) > 0:
        raise Exception('\n'.join(errors))

    return query


def _request(query):
    url = DOCKERFINDER_URL + SEARCH_ENDPOINT
    _log.debug('prepare request on endpoint {}'.format(url))
    ret = requests.get(url, params=query,
                       headers={'Accept': 'applicaiton/json',
                                'Content-type': 'application/json'})

    _log.debug('request done on url {}'.format(ret.url))
    json = ret.json()
    if 'images' in json:
        return json
    raise Exception('Dockerfinder server error')


def _choose_image(images, interactive=False):
    if interactive:
        print_('{:<3}{:<30}{:>15}{:>15}{:>15}'.format(
               '#', 'NAME', 'SIZE', 'PULLS', 'STARS'))
        for index, image in enumerate(images[:10]):
            print_('{1:<3}{0[name]:<30}{0[size]:>15}'
                   '{0[pulls]:>15}{0[stars]:>15}'.format(image, index+1))

        i = None
        while not isinstance(i, int):
            try:
                i = int(input('select an image number ')) - 1
                if i < 1 and i > 10:
                    raise Exception
                return images[i]
            except Exception:
                print_('must be a number')
    else:
        return images[0] if len(images) > 0 else None


def _complete(node, node_yaml, tosca,
              policy=None, constraints=None, interactive=False):
    properties = node.entity_tpl['properties']\
                 if 'properties' in node.entity_tpl else {}
    query = _build_query(properties, policy, constraints)
    _log.debug('query {}'.format(query))

    responce = _request(query)
    images = responce['images']
    _log.debug('returned images..')

    if len(images) < 1:
        raise Exception('no image found for container "{}"'.format(node.name))

    print_('founded {[count]} images for "{.name}"'
           ' component'.format(responce, node))

    image = _choose_image(images, interactive)

    node_yaml['artifacts'] = {
        'my_image': {
            'file': image['name'],
            'type': 'tosker.artifacts.Image',
            'repository': 'docker_hub'
        }
    }
    print_('complete node "{}" with image "{}" ({:.2f} MB, {} pulls, {} stars)'
           ''.format(node.name, image['name'],
                     image['size'] / 1000000, image['pulls'], image['stars']))


def _write_updates(tosca, new_path):
    with open(new_path, "w") as f:
        ruamel.yaml.round_trip_dump(tosca, f,
                                    # width=80,
                                    # indent=2,
                                    # block_seq_indent=2,
                                    # top_level_colon_align=True
                                    )


def _gen_new_path(file_path, mod):
    points = file_path.split('.')
    return '{}.{}.{}'.format(''.join(points[:-1]), mod, points[-1])


def _check_components(tosca, components):
    if hasattr(tosca, 'nodetemplates'):
        if tosca.nodetemplates:
            for c in components:
                correct = False
                for n in tosca.nodetemplates:
                    if c == n.name:
                        correct = True
                if not correct:
                    raise Exception('component "{}" not founded'.format(c))


def _update_tosca(file_path, new_path,
                  components=[], policy=None,
                  constraints={}, interactive=False):
    _log.debug('update TOSCA YAML file {} to {}'.format(file_path, new_path))

    tosca = ToscaTemplate(file_path)
    path_name = path.dirname(file_path)
    name = tosca.input_path.split('/')[-1][:-5]

    _check_components(tosca, components)

    tosca_yaml = ruamel.yaml.round_trip_load(open(file_path),
                                             preserve_quotes=True)

    errors = []
    to_complete = False
    if hasattr(tosca, 'nodetemplates'):
        if tosca.nodetemplates:
            for node in tosca.nodetemplates:
                if len(components) == 0 or node.name in components:
                    if _is_abstract(node):
                        to_complete = True
                        _log.debug('node {.name} is abstract'.format(node))
                        node_yaml = tosca_yaml['topology_template'][
                            'node_templates'][node.name]
                        try:
                            _complete(node, node_yaml, tosca,
                                      policy, constraints, interactive)
                        except Exception as e:
                            _log.error('error: {}'.format(
                                        traceback.format_exc()))
                            errors.append(' '.join(e.args))

    if len(errors) == 0 and to_complete:
        _write_updates(tosca_yaml, new_path)
    elif len(errors) > 0:
        print_('ERRORS:\n{}'.format('\n'.join(errors)))
    else:
        print_('no abstract node founded')


def _set_logger(level=logging.DEBUG):
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter((
        '%(levelname) -3s %(asctime)s %(name)'
        '-3s %(funcName)'
        '-1s %(lineno) -0s: %(message)s'
    ))
    ch.setFormatter(formatter)
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    log.addHandler(ch)
    return log


_USAGE = '''
tosker-matcher FILE [COMONENT..] [OPTIONS]
tosker-matcher --help|-h
tosker-matcher --version|-v

FILE
  TOSCA YAML file or a CSAR to completed

COMONENT
  a ist of component to complete (by default all component are considered)

OPTIONS
  --debug               active debug mode
  -q|--quiet            active quiet mode
  -i|--interactive      active interactive mode
  --constraints=value   constraint to give to DockerFinder
                        (i.e. --constraints 'size<=100MB pulls>30 stars>10')
  --policy=top|size     ordering of the images
'''

_FLAG = {
    '--debug': 'debug',
    '-q': 'quiet',
    '--quiet': 'quiet',
    '--help': 'help',
    '-h': 'help',
    '-v': 'version',
    '--version': 'version',
    '-i': 'interactive',
    '--interactive': 'interactive'
}

_PARAMS = ['--policy', '--constraints']


def _parse_input(args):
    inputs = {}
    comps = []
    flags = {}
    file = ''
    p1 = re.compile('--.*')
    p2 = re.compile('-.?')

    def check_file(file):
        file_name = None
        if path.isfile(file):
            if file.endswith(('.yaml', '.csar', '.CSAR', '.YAML')):
                file_name = file
        return file_name

    def get_value(i):
        value = []
        old_i = i
        while i < len(args) and not p1.match(args[i]) and not p1.match(args[i]):
            i += 1
        return ' '.join(args[old_i:i-1]), i-1

    i = 0
    while i < len(args):
        if p1.match(args[i]):
            if _FLAG.get(args[i], False):
                flags[_FLAG[args[i]]] = True
            elif args[i] in _PARAMS:
                if (i + 1 < len(args) and
                   not p1.match(args[i + 1]) and
                   not p2.match(args[i + 1])):
                    value, new_i = get_value(i+1)
                    inputs[args[i][2:]] = value
                    i = new_i
                    continue
                else:
                    raise Exception('missing input value for {}'.format(
                          args[i]))
            else:
                raise Exception('parameter {} not recognise'.format(args[i]))
        elif p2.match(args[i]):
            if _FLAG.get(args[i], False):
                flags[_FLAG[args[i]]] = True
            else:
                raise Exception('known parameter.')
        elif args[i] and file:
            comps.append(args[i])
        elif i == 0:
            file = check_file(args[i])
            if file is None:
                raise Exception('first argument must be a TOSCA yaml file, '
                                'a CSAR or a ZIP archive.')
        i += 1
    return file, comps, flags, inputs


def _parse_contraint(con):
    ret = {}
    size_re = re.compile('(?<=size)\s*(>|<|=|>=|<=)\s*[0-9]+[A-z]+')
    pulls_re = re.compile('(?<=pulls)\s*(>|<|=|>=|<=)\s*[0-9]+')
    stars_re = re.compile('(?<=stars)\s*(>|<|=|>=|<=)\s*[0-9]+')

    size = size_re.search(con)
    if size is not None:
        ret['size'] = size.group(0)

    pulls = pulls_re.search(con)
    if pulls is not None:
        ret['pulls'] = pulls.group(0)

    stars = stars_re.search(con)
    if stars is not None:
        ret['stars'] = stars.group(0)

    return ret


def run():
    global _log
    if len(argv) > 1:
        try:
            file_path, comps, flags, inputs = _parse_input(argv[1:])
            # print_('parsed: {}, {}, {}, {}'.format(file_path, comps, flags, inputs))
        except Exception as e:
            print_(''.join(e.args))
            exit(-1)
    else:
        print_('few arguments, --help for usage')
        exit(-1)

    if flags.get('help', False):
        print_(_USAGE)
        exit(0)
    if flags.get('version', False):
        print_(__version__)
        exit(0)
    if flags.get('debug', False):
        _log = _set_logger(logging.DEBUG)
    else:
        _log = _set_logger(logging.CRITICAL)
    if flags.get('quiet', False):
        # TODO: implement quiet
        pass

    constraint = inputs.get('constraints', {})
    _log.debug('constraints {}'.format(constraint))
    if len(constraint) > 0:
        constraint = _parse_contraint(constraint)
        _log.debug('constr_dit {}'.format(constraint))

    policy = inputs.get('policy', None)
    _log.debug('policy {}'.format(policy))
    if policy is not None and policy != POLICY_TOP and policy != POLICY_SIZE:
        print_('policy must be "{}" or "{}"'.format(POLICY_TOP, POLICY_SIZE))
        exit(-1)

    global DOCKERFINDER_URL
    DOCKERFINDER_URL = os.environ.get('DOCKERFINDER_URL', DOCKERFINDER_URL)

    try:
        if file_path.endswith(('.zip', '.csar')):
            _log.debug('CSAR founded')
            csar_tmp_path, yaml_path = _unpack_csar(file_path)
            _update_tosca(yaml_path, yaml_path,
                          components=comps, policy=policy,
                          constraints=constraint,
                          interactive=flags.get('interactive', False))
            new_path = _gen_new_path(file_path, 'completed')
            _pack_csar(csar_tmp_path, new_path)
        else:
            _log.debug('YAML founded')
            new_path = _gen_new_path(file_path, 'completed')
            _update_tosca(file_path, new_path,
                          components=comps, policy=policy,
                          constraints=constraint,
                          interactive=flags.get('interactive', False))
    except Exception as e:
        _log.error('error: {}'.format(traceback.format_exc()))
        print_(' '.join(e.args))


def _unpack_csar(file_path):
    # Work around bug validation csar of toscaparser
    csar = CSAR(file_path)
    try:
        csar.validate()
    except ValueError as e:
        # _log.debug(e)
        if not str(e).startswith("The resource") or \
           not str(e).endswith("does not exist."):
            raise e

    csar.decompress()

    yaml_path = path.join(csar.temp_dir, csar.get_main_template())
    return (csar.temp_dir, yaml_path)


def _pack_csar(csar_tmp_path, new_path):
    _create_csar(csar_tmp_path, new_path)


def _create_csar(csar_tmp_path, path_to_save):
    # with ZipFile(path_to_save, 'w') as zp:
    #     zp.write(csar_tmp_path)
    # shutil.make_archive(path_to_save, 'zip', csar_tmp_path)

    with zipfile.ZipFile(path_to_save, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirname, subdirs, files in os.walk(csar_tmp_path):
            # zf.write(dirname, root)
            for filename in files:
                zf.write(path.join(dirname, filename),
                         path.relpath(path.join(dirname, filename),
                                      os.path.join(csar_tmp_path, '.')))


if __name__ == '__main__':
    run()
