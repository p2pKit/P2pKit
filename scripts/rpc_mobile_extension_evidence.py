"""Offline checks for new mobile campaign records. Never dispatch a device action."""

import hashlib
import ipaddress
import re

import rpc_capacity_evidence as evidence
import rpc_mobile_capacity as protocol

need = protocol.need


def review_mixed(host, raw):
    need(type(host) is dict and host.get('mode') == 'mixed' and host.get('clientCount') == 256 and
         host.get('status') == 'MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW' and
         host.get('errors') == [] and host.get('sourceUnchanged') is True and host.get('harnessUnchanged') is True and
         host.get('phoneCleanup') == dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True),
         'The original mixed coordinator must complete workload, retention, and owned Stop')
    bound = protocol.binding(host.get('mobileBinding'))
    need(bound['schema'] == '2' and bound['clientCount'] == '256')
    need(type(host.get('source')) is dict and host['source'].get('commit') == bound['hostSourceSha'])
    need(evidence.mixed_roster(host.get('measurement'), 256)['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW')
    retention = host.get('postRetention')
    need(type(retention) is dict and protocol.retention(retention.get('before'), retention.get('after')) == retention)
    plan = host.get('mixedClientPlan')
    need(type(plan) is dict and set(plan) == {
        'schema', 'scope', 'runLabel', 'runNonce', 'hostSourceSha', 'hostArtifactSha256', 'hostPlatform',
        'hostPin', 'hostAddress', 'hostPort', 'physicalClientPlatform', 'physicalClientPin',
        'physicalClientArtifactSha256',
    })
    need(all(type(value) is str for value in plan.values()) and plan['schema'] == '1' and
         plan['scope'] == 'physical-mixed-rpc-client' and
         all(plan[key] == bound[key] for key in ('runLabel', 'runNonce', 'hostSourceSha',
                                                 'hostArtifactSha256', 'hostPlatform')) and
         {plan['hostPlatform'], plan['physicalClientPlatform']} == {'Android', 'Ios'} and
         plan['hostPin'] != plan['physicalClientPin'] and
         all(re.fullmatch('p2f1-[a-z2-7]{52}', plan[key]) for key in ('hostPin', 'physicalClientPin')) and
         re.fullmatch('[a-f0-9]{64}', plan['physicalClientArtifactSha256']) and
         re.fullmatch('[1-9][0-9]{3,4}', plan['hostPort']) and 1024 <= int(plan['hostPort']) <= 65535)
    address = ipaddress.IPv4Address(plan['hostAddress'])
    need(any(address in ipaddress.IPv4Network(network)
             for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')))
    need(protocol.parse(raw) == plan | dict(verifiedReplies='20', released='true', runtimeClosed='true',
                                           temporaryTrustRemoved='true'),
         'Missing, failed, foreign or incompletely retired companion outcome')
    return dict(scope='SOURCE_BOUND_MIXED_RECORDS_PENDING_PHYSICAL_REVIEW', sourceSha=bound['hostSourceSha'],
                hostArtifactSha256=bound['hostArtifactSha256'], hostPlatform=bound['hostPlatform'],
                physicalClientPlatform=plan['physicalClientPlatform'],
                physicalClientArtifactSha256=plan['physicalClientArtifactSha256'],
                clientRecordSha256=hashlib.sha256(raw).hexdigest(), generatorClients=255, physicalClients=1,
                generatorReplies=255, phoneReplies=20, physicalQualified=False)


def review_discharge(raw, source, artifact):
    binding = protocol.parse(raw)
    fields = {'schema', 'scope', 'platform', 'runLabel', 'sourceSha', 'artifactSha256', 'requiredMillis', 'status'}
    need(fields <= set(binding) and binding['schema'] == '1' and
         binding['scope'] == 'foreground-unplugged-observations' and binding['requiredMillis'] == '1800000' and
         re.fullmatch('[a-f0-9]{40}', source) and re.fullmatch('[a-f0-9]{64}', artifact) and
         binding['sourceSha'] == source and binding['artifactSha256'] == artifact and
         re.fullmatch('discharge-[a-f0-9]{32}', binding['runLabel']) and binding['platform'] in ('Android', 'Ios'))
    status = binding['status']
    need(status in ('recording', 'complete', 'thermal-stop', 'power-changed', 'sample-gap', 'interrupted'))
    count = len(binding) - len(fields)
    need(1 <= count <= 182 and set(binding) == fields | {f'sample{index:03}' for index in range(count)})
    samples = []
    platform = binding['platform']
    for index in range(count):
        row = binding[f'sample{index:03}'].split(',')
        need(len(row) == 6 and re.fullmatch('0|[1-9][0-9]{0,18}', row[0]))
        elapsed, level, current, temperature, state, thermal = row
        elapsed = int(elapsed)
        need(elapsed < 2 ** 63 and (elapsed == 0 if index == 0 else elapsed > samples[-1]['elapsedMillis']))
        battery_source = 'android-battery-manager' if platform == 'Android' else 'ios-uidevice'
        thermal_source = 'android-power-manager' if platform == 'Android' else 'ios-process-info'
        sensors = protocol.environment(dict(
            batteryPercentMilli=level, batteryCurrentMicroamps=current, batteryTemperatureMilliC=temperature,
            batteryState=state, batterySource='unavailable' if state == 'unavailable' else battery_source,
            thermalState=thermal, thermalSource='unavailable' if thermal == 'unavailable' else thermal_source,
        ), platform)
        samples.append(dict(elapsedMillis=elapsed) | sensors)
    final = samples[-1]
    for row in samples[:-1]:
        need(row['batteryState'] == 'unplugged' and row['thermalState'] not in ('serious', 'critical'))
    if status == 'thermal-stop':
        need(final['thermalState'] in ('serious', 'critical'))
    elif status == 'power-changed':
        need(final['batteryState'] != 'unplugged' and final['thermalState'] not in ('serious', 'critical'))
    else:
        need(final['batteryState'] == 'unplugged' and final['thermalState'] not in ('serious', 'critical'))
    complete = status == 'complete'
    if complete:
        need(1_800_000 <= final['elapsedMillis'] <= 1_803_000 and
             all(0 < after['elapsedMillis'] - before['elapsedMillis'] <= 13_000
                 for before, after in zip(samples, samples[1:])), 'Incomplete unplugged sensor interval')
    start_level = samples[0]['batteryPercentMilli']
    end_level = final['batteryPercentMilli']
    return dict(scope='PUBLIC_PHONE_SENSOR_OBSERVATIONS_ONLY', status=status, sourceSha=source,
                artifactSha256=artifact, recordSha256=hashlib.sha256(raw).hexdigest(),
                platform=platform, runLabel=binding['runLabel'], completeUnpluggedInterval=complete,
                observedBatteryChangeMilliPercent=end_level - start_level
                if complete and type(start_level) is int and type(end_level) is int else None,
                calibratedEnergyMeasured=False, samples=samples)
