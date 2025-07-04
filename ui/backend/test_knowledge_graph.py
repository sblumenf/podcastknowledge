#!/usr/bin/env python3
"""Test script for knowledge graph endpoint"""

import asyncio
from routes.knowledge_graph import get_knowledge_graph

async def test():
    try:
        result = await get_knowledge_graph("mel_robbins_podcast")
        print(f"Clusters: {len(result['clusters'])}")
        print(f"Edges: {len(result['edges'])}")
        if result['clusters']:
            print(f"\nSample cluster: {result['clusters'][0]}")
        if result['edges']:
            print(f"\nSample edge: {result['edges'][0]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())