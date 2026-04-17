"""Simple usage example for the OpenBeta client."""

from pprint import pprint

from src.integrations.climbing.openbeta_client import search_areas


def main() -> None:
    results = search_areas("Smith Rock")
    pprint(results)


if __name__ == "__main__":
    main()
