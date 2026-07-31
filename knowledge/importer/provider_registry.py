"""
knowledge.importer.provider_registry

Registro oficial de proveedores de conocimiento
utilizados por HUGINN.
"""

from knowledge.importer.providers.dsn_provider import (
    DeepSpaceNetworkProvider,
)


class ProviderRegistry:
    """
    Registro centralizado de proveedores.
    """

    def __init__(self) -> None:

        self._providers = {}

        self.register(
            DeepSpaceNetworkProvider()
        )

    def register(
        self,
        provider,
    ) -> None:

        self._providers[
            provider.source_id
        ] = provider

    def get(
        self,
        source_id: str,
    ):

        return self._providers.get(
            source_id
        )

    def all(self):

        return list(
            self._providers.values()
        )

    def available(self):

        return sorted(
            self._providers.keys()
        )