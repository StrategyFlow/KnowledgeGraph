import json
with open('output/operation_bobcat_lightning_extracted.json') as f:
    d = json.load(f)
    print(f"Title: {d['title']}")
    print(f"Sections: {len(d['sections'])}")
    for s in d['sections']:
        print(f"  - {s['header']}")
    print(f"Actors: {len(d['actors'])}")
    print(f"Actor Types: {d['actor_types']}")
    print(f"Relations: {len(d['relations'])}")
    print(f"Key Tasks: {len(d['key_tasks'])}")
    print(f"Timelines: {len(d['timelines'])}")
    print(f"Commander's Intent: {'Yes' if d.get('commanders_intent') else 'No'}")
    print(f"Concept of Operations: {'Yes' if d.get('concept_of_operations') else 'No'}")
    print(f"Scheme of Fires: {'Yes' if d.get('scheme_of_fires') else 'No'}")
