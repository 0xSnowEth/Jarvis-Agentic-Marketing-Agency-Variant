# -*- coding: utf-8 -*-
"""Replace all remaining star emoji with context-specific emoji in whatsapp_operator.py"""

filepath = '/home/snowaflic/agents/whatsapp_operator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

star = '\u2726'  # ✦
star_count_before = content.count(star)
print(f'Stars before: {star_count_before}')

REPLACEMENTS = [
    ('*Operator Actions* \u2726\nChoose the next workspace or check a live system summary.',
     '*Operator Actions* \u2699\ufe0f\nChoose a workspace or check a live system summary.'),
    ('*Client Roster* \u2726\nNo clients saved yet.\n\nReply with *Add Client* to create the first one.',
     '*Client Roster* \U0001f4cb\nNo clients saved yet.\n\nReply with *Add Client* to create the first one.'),
    ('*Client Roster* \u2726',
     '*Client Roster* \U0001f4cb'),
    ('*System Status* \u2726',
     '*System Status* \U0001f7e2'),
    ('*Preview ready* \u2726\n',
     '*Preview ready* \U0001f441\ufe0f\n'),
    ('*No clients yet* \u2726\nAdd the first client before using this workflow.',
     '*No clients yet* \u26a0\ufe0f\nAdd the first client before using this workflow.'),
    ('*No clients yet* \u2726\nAdd the first client before starting a post.',
     '*No clients yet* \u26a0\ufe0f\nAdd the first client before starting a post.'),
    ('*No clients yet* \u2726\nAdd the first client before opening strategy.',
     '*No clients yet* \u26a0\ufe0f\nAdd the first client before opening strategy.'),
    ('*No clients yet* \u2726\nAdd the first client before starting Meta connect.',
     '*No clients yet* \u26a0\ufe0f\nAdd the first client before starting Meta connect.'),
    ('*Pick a client* \u2726\nChoose the client for this post. If the list does not load, reply with the client name.',
     '*Select Client* \U0001f4cb\nWhich client is this post for? If the list doesn\u2019t load, reply with the client name.'),
    ('*Pick a client* \u2726\nChoose the client for these assets. I have the files and I am ready to build once you pick.',
     '*Select Client* \U0001f4ce\nI have the files ready. Pick the client and I\u2019ll start building the draft.'),
    ('*Pick a client* \u2726\nJarvis will generate the Meta connect handoff after you select the client.',
     '*Select Client* \U0001f517\nJarvis will generate the Meta connect link right after you pick.'),
    ('*Pick a client* \u2726\nJarvis will open the planning prompt right after the client is selected.',
     '*Select Client* \U0001f4ca\nJarvis will open the strategy workspace right after you pick.'),
    ('*Choose a client* \u2726\nReply with the client name if the list does not load.',
     '*Select Client* \U0001f4cb\nReply with the client name if the list does not load.'),
    ('*New post for ', '*New post* \U0001f4dd \u2014 '),
    ('* \u2726\nSend the image or video as *WhatsApp Document*',
     '\nSend the image or video as *WhatsApp Document*'),
    ('*Strategy for ', '*Strategy prompt* \U0001f4ca \u2014 '),
    ('* \u2726\nTell Jarvis what to plan.',
     '\nTell Jarvis what to plan.'),
    ('*No saved plans for ', '*No saved plans* \U0001f4ca \u2014 '),
    ('* \u2726\nBuild a new research-backed plan first',
     '\nBuild a new research-backed plan first'),
    ('*Saved plans for ', '*Saved plans* \U0001f4ca \u2014 '),
    ('* \u2726\nOpen any plan below to review the research-backed strategy again.',
     '\nOpen any plan below to review the research-backed strategy.'),
    ('*Edit needs a caption* \u2726',
     '*Edit needs a caption* \u270f\ufe0f'),
    ('*Hashtag edit needs tags* \u2726',
     '*Hashtag edit needs tags* \u270f\ufe0f'),
    ('*Choose Release Mode* \u2726',
     '*Choose Release Mode* \U0001f4c5'),
    ('*Meta status refreshed* \u2726',
     '*Meta status refreshed* \u2705'),
    ('*I need the original file* \u2726',
     '*I need the original file* \U0001f4e4'),
    ('*Preview still open* \u2726',
     '*Preview still open* \u23f3'),
    ('*Flow cancelled* \u2726',
     '*Flow cancelled* \u2716'),
    ('*Nothing to cancel* \u2726',
     '*Nothing to cancel* \u2139\ufe0f'),
    ('*Client build still running* \u2726',
     '*Client build still running* \u23f3'),
    ('*Client brief still open* \u2726',
     '*Client brief still open* \U0001f4dd'),
    ('*Brief received for ', '*Brief received* \U0001f3e2 \u2014 '),
    ('* \u2726\nJarvis is building the full brand profile',
     '\nJarvis is building the full brand profile'),
    ('*Notes saved* \u2726',
     '*Notes saved* \U0001f4cc'),
    ('*Bundle notes updated* \u2726',
     '*Bundle notes updated* \U0001f4cc'),
]

replaced = 0
for old, new in REPLACEMENTS:
    occurrences = content.count(old)
    if occurrences > 0:
        content = content.replace(old, new)
        replaced += occurrences
        print(f'  OK ({occurrences}x): {repr(old[:50])}')

star_count_after = content.count(star)
print(f'\nStars after: {star_count_after}')
print(f'Total replacements made: {replaced}')

if star_count_after > 0:
    # Find remaining stars
    for i, line in enumerate(content.split('\n'), 1):
        if star in line:
            print(f'  Remaining at line {i}: {line.strip()[:80]}')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('File saved.')
