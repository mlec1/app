import urllib
from email.message import Message

from app.email import headers
from app.email_utils import add_or_replace_header
from app.handler.unsubscribe_encoder import (
    UnsubscribeEncoder,
    UnsubscribeAction,
    UnsubscribeData,
    UnsubscribeOriginalData,
)
from app.models import Alias, Contact, UnsubscribeBehaviourEnum


class UnsubscribeGenerator:
    def _generate_header_with_sl_behaviour(
        self, alias: Alias, contact: Contact, message: Message
    ) -> Message:
        """
        Add List-Unsubscribe header
        """
        user = alias.user
        if user.one_click_unsubscribe_block_sender:
            unsub = UnsubscribeData(UnsubscribeAction.DisableContact, contact.id)
        else:
            unsub = UnsubscribeData(UnsubscribeAction.DisableAlias, alias.id)
        return self._add_unsubscribe_header(message, unsub)

    def _generate_header_with_original_behaviour(
        self, alias: Alias, message: Message
    ) -> Message:
        unsubscribe_data = message[headers.LIST_UNSUBSCRIBE]
        if not unsubscribe_data:
            return message
        raw_methods = [method.strip() for method in unsubscribe_data.split(",")]
        mailto_unsubs = None
        other_unsubs = []
        for raw_method in raw_methods:
            start = raw_method.find("<")
            end = raw_method.rfind(">")
            if start == -1 or end == -1 or start >= end:
                continue
            method = raw_method[start + 1 : end]
            url_data = urllib.parse.urlparse(method)
            if url_data.scheme == "mailto":
                query_data = urllib.parse.parse_qs(url_data.query)
                mailto_unsubs = (url_data.path, query_data.get("subject", [""])[0])
            else:
                other_unsubs.append(method)
        # If there are non mailto unsubscribe methods, use those in the header
        if other_unsubs:
            add_or_replace_header(
                message,
                headers.LIST_UNSUBSCRIBE,
                ", ".join([f"<{method}>" for method in other_unsubs]),
            )
            add_or_replace_header(
                message, headers.LIST_UNSUBSCRIBE_POST, "List-Unsubscribe=One-Click"
            )
            return message
        return self._add_unsubscribe_header(
            message,
            UnsubscribeData(
                UnsubscribeAction.OriginalUnsubscribeMailto,
                UnsubscribeOriginalData(alias.id, mailto_unsubs[0], mailto_unsubs[1]),
            ),
        )

    def _add_unsubscribe_header(
        self, message: Message, unsub: UnsubscribeData
    ) -> Message:
        unsub_link = UnsubscribeEncoder.encode(unsub.action, unsub.data)

        add_or_replace_header(message, headers.LIST_UNSUBSCRIBE, f"<{unsub_link.link}>")
        if not unsub_link.via_email:
            add_or_replace_header(
                message, headers.LIST_UNSUBSCRIBE_POST, "List-Unsubscribe=One-Click"
            )
        return message

    def add_header_to_message(
        self, alias: Alias, contact: Contact, message: Message
    ) -> Message:
        """
        Add List-Unsubscribe header
        """
        if alias.user.unsub_behaviour == UnsubscribeBehaviourEnum.PreserveOriginal:
            return self._generate_header_with_original_behaviour(alias, message)
        else:
            return self._generate_header_with_sl_behaviour(alias, contact, message)
