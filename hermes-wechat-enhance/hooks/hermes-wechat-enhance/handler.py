from hermes_wechat_enhance.store import MessageStore

_store = MessageStore()


async def handle(event_type, context):
    if event_type == "agent:start":
        _store.append_inbound(context)
    elif event_type == "agent:end":
        _store.append_outbound(context)
    return None
