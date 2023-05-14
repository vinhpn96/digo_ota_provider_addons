import asyncio
import aiohttp
import async_timeout
from matter_server.client import MatterClient
from chip.clusters import Objects as clusters
from matter_server.common.models import EventType
from matter_server.client.models.node import MatterNode, MatterEndpoint
import time
import logging
from matter_server.common.helpers.util import (
    chip_clusters_version,
    dataclass_from_dict,
    dataclass_to_dict,
)

LOGGER = logging.getLogger(__name__)

port = 5580
# urlMatterServer = f"http://192.168.63.104:{port}/ws"
urlMatterServer = f"http://192.168.0.103:{port}/ws"
FABRIC_INDEX = 2
SETUP_PIN_CODE = 20202021
CASE_ADMIN_NODE = 112233

async def announceOtaProvider(client : MatterClient,
                                req_endpoint : MatterEndpoint,
                                pro_endpoint : MatterEndpoint,
                                vendorId: int = 0,
                                announcementReason: clusters.OtaSoftwareUpdateRequestor.Enums.OTAAnnouncementReason = 0
                            ):
    LOGGER.error(f"announceOtaProvider to node_id={req_endpoint.node.node_id}")
    return await client.send_device_command(node_id=req_endpoint.node.node_id, endpoint_id=req_endpoint.endpoint_id,
        command=clusters.OtaSoftwareUpdateRequestor.Commands.AnnounceOtaProvider(
            providerNodeId=pro_endpoint.node.node_id,
            endpoint=pro_endpoint.endpoint_id
        )
    )
    

async def writeAccessControlACL(client : MatterClient, endpoint : MatterEndpoint):
    LOGGER.error(f"writeAccessControlACL to provider node_id={endpoint.node.node_id}")
    endpoint_acl : MatterEndpoint = await getAccessControlEndpoint(endpoint.node)
    if endpoint_acl is None:
        return
    payload = {
        'value': [
            {
                'privilege': clusters.AccessControl.Enums.Privilege.kAdminister,
                'authMode': clusters.AccessControl.Enums.AuthMode.kCase, 
                'subjects': [CASE_ADMIN_NODE], 
                'targets': [],
                'fabricIndex': FABRIC_INDEX,
                '_type': 'chip.clusters.Objects.AccessControl.Structs.AccessControlEntry'
            },
            {
                'privilege': clusters.AccessControl.Enums.Privilege.kOperate,
                'authMode': clusters.AccessControl.Enums.AuthMode.kCase, 
                'subjects': [], 
                'targets': [], 
                'fabricIndex': FABRIC_INDEX,
                '_type': 'chip.clusters.Objects.AccessControl.Structs.AccessControlEntry'
            }
        ]
    }
    return await client.send_command("write_attribute",
                            node_id=endpoint.node.node_id,
                            endpoint_id=endpoint_acl.endpoint_id,
                            cluster_id = clusters.AccessControl.id,
                            attribute_name=clusters.AccessControl.Attributes.Acl.__name__,
                            payload=payload,
    )

async def writeDefaultOtaProviders(client : MatterClient,
                                   pro_node_id : int,
                                   pro_endpoint: int,
                                   req_node_id : int,
                                   req_endpoint: int):
    LOGGER.error(f"writeDefaultOtaProviders to requestor[node_id={req_node_id} endpoint={req_endpoint}] "
                  f"with provider [node_id={pro_node_id} endpoint={pro_endpoint}]")
    payload = {
        "value": [
            {
                "providerNodeID": pro_node_id,
                "endpoint": pro_endpoint,
                "fabricIndex": FABRIC_INDEX,
                '_type': 'chip.clusters.Objects.OtaSoftwareUpdateRequestor.Structs.ProviderLocation'
            }
        ]
    }
    return await client.send_command("write_attribute",
                            node_id=req_node_id,
                            endpoint_id=req_endpoint,
                            cluster_id=clusters.OtaSoftwareUpdateRequestor.id,
                            attribute_name=clusters.OtaSoftwareUpdateRequestor.Attributes.DefaultOtaProviders.__name__,
                            payload=payload,
    )

async def getOtaProvider(client : MatterClient) -> MatterEndpoint:
    endpoint = next(
        (
            endpoint
            for node in await client.get_nodes()
            for endpoint in node.endpoints.values()
            if endpoint.has_cluster(clusters.OtaSoftwareUpdateProvider)
        ),
        None,
    )
    return endpoint

async def getOtaRequestorEndpoint(node: MatterNode) -> MatterEndpoint:
    endpoint = next(
        (
            endpoint
            for endpoint in node.endpoints.values()
            if endpoint.has_cluster(clusters.OtaSoftwareUpdateRequestor)
        ),
        None,
    )
    return endpoint

async def getAccessControlEndpoint(node: MatterNode) -> MatterEndpoint:
    endpoint = next(
        (
            endpoint
            for endpoint in node.endpoints.values()
            if endpoint.has_cluster(clusters.AccessControl)
        ),
        None,
    )
    return endpoint

async def monitorTask(client : MatterClient):
    otaProviderEndpoint : MatterEndpoint = None
    while True:
        otaProviderEndpoint = await getOtaProvider(client)
        if otaProviderEndpoint != None:
            LOGGER.error(f"OTA Provider: node_id={otaProviderEndpoint.node.node_id} "
                        f"endpoint_id={otaProviderEndpoint.endpoint_id}")
            break
        LOGGER.error("Provider's not available. We have to commisstion on network")
        await client.commission_on_network(SETUP_PIN_CODE)
        time.sleep(60)
    await writeAccessControlACL(client, otaProviderEndpoint)

    async def setup_node(node : MatterNode):
        LOGGER.error(f"setup_node: node_id={node.node_id}")
        req_endpoint = await getOtaRequestorEndpoint(node)
        if req_endpoint != None:
            await writeDefaultOtaProviders(client,
                        otaProviderEndpoint.node.node_id,
                        otaProviderEndpoint.endpoint_id,
                        node.node_id, req_endpoint.endpoint_id)
            time.sleep(30)
            await announceOtaProvider(client=client, req_endpoint=req_endpoint, pro_endpoint=otaProviderEndpoint)
    for node in await client.get_nodes():
            await setup_node(node)

    async def node_added_callback(event: EventType, node: MatterNode) -> None:
        """Handle node added event."""
        await setup_node(node)

    client.subscribe(node_added_callback, EventType.NODE_ADDED)
    while True:
        time.sleep(60)

async def main():
    async with aiohttp.ClientSession() as session:
        async with MatterClient(urlMatterServer, session) as matter_client:
            isConnected = False
            while isConnected == False:
                try:
                    await matter_client.connect()
                    isConnected = True
                except Exception as err:
                    print(err)
                    time.sleep(10)
            init_ready = asyncio.Event()
            listen_task = asyncio.create_task(matter_client.start_listening(init_ready))
            try:
                async with async_timeout.timeout(30):
                    await init_ready.wait()
            except asyncio.TimeoutError as err:
                listen_task.cancel()
                raise ConfigEntryNotReady("Matter client not ready") from err
            await monitorTask(matter_client)

asyncio.run(main())
