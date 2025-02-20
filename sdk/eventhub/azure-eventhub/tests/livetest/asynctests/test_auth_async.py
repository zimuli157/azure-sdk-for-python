# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
import pytest
import asyncio
import time

from azure.core.credentials import AzureSasCredential, AzureNamedKeyCredential
from azure.identity.aio import EnvironmentCredential
from azure.eventhub import EventData
from azure.eventhub.aio import (
    EventHubConsumerClient,
    EventHubProducerClient,
    EventHubSharedKeyCredential,
)
from azure.eventhub.aio._client_base_async import EventHubSASTokenCredential


@pytest.mark.liveTest
@pytest.mark.asyncio
async def test_client_token_credential_async(live_eventhub, get_credential_async, uamqp_transport):
    credential = get_credential_async()
    producer_client = EventHubProducerClient(
        fully_qualified_namespace=live_eventhub["hostname"],
        eventhub_name=live_eventhub["event_hub"],
        credential=credential,
        user_agent="customized information",
        auth_timeout=30,
        uamqp_transport=uamqp_transport,
    )
    consumer_client = EventHubConsumerClient(
        fully_qualified_namespace=live_eventhub["hostname"],
        eventhub_name=live_eventhub["event_hub"],
        consumer_group="$default",
        credential=credential,
        user_agent="customized information",
        auth_timeout=30,
        uamqp_transport=uamqp_transport,
    )

    async with producer_client:
        batch = await producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await producer_client.send_batch(batch)

    async def on_event(partition_context, event):
        on_event.called = True
        on_event.partition_id = partition_context.partition_id
        on_event.event = event

    on_event.called = False
    async with consumer_client:
        task = asyncio.ensure_future(consumer_client.receive(on_event, partition_id="0", starting_position="-1"))
        await asyncio.sleep(15)
    await task
    assert on_event.called is True
    assert on_event.partition_id == "0"
    assert list(on_event.event.body)[0] == "A single message".encode("utf-8")


@pytest.mark.liveTest
@pytest.mark.asyncio
async def test_client_sas_credential_async(live_eventhub, uamqp_transport):
    # This should "just work" to validate known-good.
    hostname = live_eventhub["hostname"]
    producer_client = EventHubProducerClient.from_connection_string(
        live_eventhub["connection_str"],
        eventhub_name=live_eventhub["event_hub"],
        uamqp_transport=uamqp_transport,
    )

    async with producer_client:
        batch = await producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await producer_client.send_batch(batch)

    # This should also work, but now using SAS tokens.
    credential = EventHubSharedKeyCredential(live_eventhub["key_name"], live_eventhub["access_key"])
    auth_uri = "sb://{}/{}".format(hostname, live_eventhub["event_hub"])
    token = (await credential.get_token(auth_uri)).token
    producer_client = EventHubProducerClient(
        fully_qualified_namespace=hostname,
        eventhub_name=live_eventhub["event_hub"],
        credential=EventHubSASTokenCredential(token, time.time() + 3000),
        uamqp_transport=uamqp_transport,
    )

    async with producer_client:
        batch = await producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await producer_client.send_batch(batch)

    # Finally let's do it with SAS token + conn str
    token_conn_str = "Endpoint=sb://{}/;SharedAccessSignature={};".format(hostname, token)
    conn_str_producer_client = EventHubProducerClient.from_connection_string(
        token_conn_str,
        eventhub_name=live_eventhub["event_hub"],
        uamqp_transport=uamqp_transport,
    )

    async with conn_str_producer_client:
        batch = await conn_str_producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await conn_str_producer_client.send_batch(batch)


@pytest.mark.liveTest
@pytest.mark.asyncio
async def test_client_azure_sas_credential_async(live_eventhub, uamqp_transport):
    # This should "just work" to validate known-good.
    hostname = live_eventhub["hostname"]
    producer_client = EventHubProducerClient.from_connection_string(
        live_eventhub["connection_str"],
        eventhub_name=live_eventhub["event_hub"],
        uamqp_transport=uamqp_transport,
    )

    async with producer_client:
        batch = await producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await producer_client.send_batch(batch)

    credential = EventHubSharedKeyCredential(live_eventhub["key_name"], live_eventhub["access_key"])
    auth_uri = "sb://{}/{}".format(hostname, live_eventhub["event_hub"])
    token = (await credential.get_token(auth_uri)).token
    producer_client = EventHubProducerClient(
        fully_qualified_namespace=hostname,
        eventhub_name=live_eventhub["event_hub"],
        auth_timeout=30,
        credential=AzureSasCredential(token),
        uamqp_transport=uamqp_transport,
    )

    async with producer_client:
        batch = await producer_client.create_batch(partition_id="0")
        batch.add(EventData(body="A single message"))
        await producer_client.send_batch(batch)

    assert (await producer_client.get_eventhub_properties()) is not None


@pytest.mark.liveTest
@pytest.mark.asyncio
async def test_client_azure_named_key_credential_async(live_eventhub, uamqp_transport):

    credential = AzureNamedKeyCredential(live_eventhub["key_name"], live_eventhub["access_key"])
    consumer_client = EventHubConsumerClient(
        fully_qualified_namespace=live_eventhub["hostname"],
        eventhub_name=live_eventhub["event_hub"],
        consumer_group="$default",
        credential=credential,
        auth_timeout=30,
        user_agent="customized information",
        uamqp_transport=uamqp_transport,
    )

    assert (await consumer_client.get_eventhub_properties()) is not None

    credential.update("foo", "bar")

    with pytest.raises(Exception):
        await consumer_client.get_eventhub_properties()

    credential.update(live_eventhub["key_name"], live_eventhub["access_key"])
    assert (await consumer_client.get_eventhub_properties()) is not None
