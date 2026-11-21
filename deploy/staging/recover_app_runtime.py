"""Recover an app-only Compose/rollback definition from saved Docker inspection.

Private input/output only. No secret generation, container recreation or store changes.
"""
import argparse
import json
import os
from pathlib import Path


def recover(directory: Path):
    obj = json.loads((directory / 'app.inspect.json').read_text())
    config, host = obj['Config'], obj['HostConfig']
    environment = config['Env']
    if any('\n' in item or '\r' in item for item in environment):
        raise ValueError('Multiline environment needs explicit recovery; refusing lossy env-file output')
    directory.chmod(0o700)
    env = directory / 'app.env'
    env.write_text('\n'.join(environment) + '\n')
    env.chmod(0o600)
    service = {
        'image': obj['Image'], 'command': config['Cmd'],
        'env_file': [{'path': str(env.resolve()), 'format': 'raw'}],
        'restart': host['RestartPolicy']['Name'],
        'networks': {}, 'volumes': [],
        'logging': {'driver': host['LogConfig']['Type'], 'options': host['LogConfig']['Config']},
        'labels': {k: v for k, v in config['Labels'].items() if not k.startswith('com.docker.compose.')},
    }
    if config.get('Entrypoint'):
        service['entrypoint'] = config['Entrypoint']
    for source, target in [('User', 'user'), ('WorkingDir', 'working_dir')]:
        if config.get(source):
            service[target] = config[source]
    for source, target in [('Memory', 'mem_limit'), ('MemorySwap', 'memswap_limit'),
                           ('PidsLimit', 'pids_limit'), ('ShmSize', 'shm_size')]:
        if host.get(source):
            service[target] = host[source]
    if host.get('NanoCpus'):
        service['cpus'] = host['NanoCpus'] / 1_000_000_000
    service['read_only'] = host['ReadonlyRootfs']
    for source, target in [('SecurityOpt', 'security_opt'), ('CapAdd', 'cap_add'),
                           ('CapDrop', 'cap_drop'), ('ExtraHosts', 'extra_hosts'), ('Dns', 'dns')]:
        if host.get(source):
            service[target] = host[source]
    if host.get('Privileged') or host.get('PortBindings') or host.get('Devices'):
        raise ValueError('Unexpected privileged/published/device configuration; review instead of guessing')
    health = config.get('Healthcheck')
    if health:
        service['healthcheck'] = {'test': health['Test']}
        for source, target in [('Interval', 'interval'), ('Timeout', 'timeout'),
                               ('StartPeriod', 'start_period'), ('StartInterval', 'start_interval')]:
            if health.get(source):
                service['healthcheck'][target] = f'{health[source]}ns'
        if health.get('Retries') is not None:
            service['healthcheck']['retries'] = health['Retries']
    compose = {'name': 'learnhouse-staging', 'services': {'app': service}, 'networks': {}, 'volumes': {}}
    for name, network in obj['NetworkSettings']['Networks'].items():
        compose['networks'][name] = {'external': True, 'name': name}
        service['networks'][name] = {'aliases': network.get('Aliases') or ['app']}
    for mount in obj['Mounts']:
        if mount['Type'] != 'volume':
            raise ValueError('Expected the baked app with content volume only; review other mounts')
        name = mount['Name']
        compose['volumes'][name] = {'external': True, 'name': name}
        service['volumes'].append({'type': 'volume', 'source': name, 'target': mount['Destination'],
                                   'read_only': not mount['RW']})
    output = directory / 'rollback.compose.json'
    output.write_text(json.dumps(compose, indent=2) + '\n')
    output.chmod(0o600)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    print(f'Recovered app-only rollback configuration: {recover(args.directory)}')
