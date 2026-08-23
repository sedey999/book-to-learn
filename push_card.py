#!/usr/bin/env python3
"""
Push progress management for book-to-learn.
Parameterized by --book <slug> (each book has its own data dir).

Subcommands:
  status --book <slug>                     Show push progress.
  next --book <slug> [--force]             Get next card payload as JSON.
  mark --book <slug> <id> <status>         Update progress.json.
  weekday                                  Exit 0 if Mon-Fri else 1.
  list-books                               List all books set up.

All data lives under books/<slug>/.

Design notes:
- items.json is the single source of truth. cards/*.html are preview-only
  and are NEVER parsed to recover content (historically this silently
  dropped markdown URLs and desynced from items.json).
- A lock file guards next->mark so a re-triggered cron run cannot push
  the same card twice in one day.
- mark fail does not inflate push statistics: only successes count.
"""
import json, os, sys, re, html, argparse, datetime

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKS_DIR = os.path.join(SKILL_DIR, 'books')

def book_dir(slug):
    return os.path.join(BOOKS_DIR, slug)

def load_json(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(p, obj):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def today_str():
    return datetime.date.today().isoformat()

def is_workday(d=None):
    d = d or datetime.date.today()
    return d.weekday() < 5

def out(obj):
    """Print a JSON line (always parseable by the cron agent)."""
    print(json.dumps(obj, ensure_ascii=False))

def check_unique_ids(items):
    """Raise ValueError listing duplicate ids in items.json."""
    seen, dups = set(), []
    for it in items:
        i = it.get('id')
        if i in seen and i not in dups:
            dups.append(i)
        seen.add(i)
    if dups:
        raise ValueError('duplicate ids in items.json: %s' % ', '.join(map(str, dups)))

def get_next_index(progress, index):
    last_id = progress.get('lastPushedId')
    items = index['items']
    if not last_id:
        return 0
    last_fn = 'card_%s.html' % last_id  # match filename format in index
    try:
        pos = items.index(last_fn)
    except ValueError:
        return 0
    nxt = pos + 1
    return None if nxt >= len(items) else nxt

def extract_card_id(filename):
    m = re.match(r'card_(.+)\.html', filename)
    return m.group(1) if m else None

def acquire_lock(bd, card_id):
    """Return True if we may push card_id now; False if another run is
    mid-flight (lock exists and is fresh) or this card was already
    delivered today."""
    lock_path = os.path.join(bd, '.push_lock')
    today = today_str()
    if os.path.exists(lock_path):
        try:
            lock = load_json(lock_path)
        except Exception:
            lock = {}
        # stale lock from a previous day -> takeover
        if lock.get('date') != today:
            os.remove(lock_path)
        else:
            if lock.get('cardId') == card_id and lock.get('done'):
                return False  # already delivered today
            if not lock.get('done'):
                return False  # another run mid-flight today
            # done for a different card today (only possible with --force)
            os.remove(lock_path)
    save_json(lock_path, {'date': today, 'cardId': card_id, 'done': False,
                          'ts': datetime.datetime.now().isoformat(timespec='seconds')})
    return True

def release_lock(bd, card_id, done=True):
    lock_path = os.path.join(bd, '.push_lock')
    save_json(lock_path, {'date': today_str(), 'cardId': card_id, 'done': done,
                          'ts': datetime.datetime.now().isoformat(timespec='seconds')})

def build_payload(bd, book_slug, card_id, filename, nxt):
    """Build the next-card payload from items.json (single source of truth)."""
    items = load_json(os.path.join(bd, 'items.json'))
    item = next((it for it in items if it.get('id') == card_id), None)
    if item is None:
        raise ValueError('card id %r not found in items.json (stale index.json? re-run gen-index)' % card_id)
    index = load_json(os.path.join(bd, 'index.json'))
    config = load_json(os.path.join(bd, 'config.json'))
    payload = {
        'nextId': card_id,
        'filename': filename,
        'cardIndex': nxt + 1,
        'totalCards': index.get('totalCards', '?'),
        'bookTitle': index.get('bookTitle', ''),
        'bookSlug': book_slug,
        'chapter': item.get('chapter', ''),
        'topic': item.get('topic', ''),
        'coreIdea': item.get('coreIdea', ''),
        'explanation': item.get('explanation', ''),
        'quote': item.get('quote', ''),
        'application': item.get('application', ''),
        'image': item.get('image', ''),
        'relatedLinks': item.get('relatedLinks', []),
        'terminology': item.get('terminology', []),
        'source': item.get('link', '') or index.get('bookSource', ''),
        'language': config.get('language', 'en'),
        'pushMethod': config.get('pushMethod', 'ima'),
        'date': today_str(),
        'bookDir': bd,
        'configPath': os.path.join(bd, 'config.json'),
    }
    return payload

def cmd_status(args):
    bd = book_dir(args.book)
    progress = load_json(os.path.join(bd, 'progress.json'))
    index = load_json(os.path.join(bd, 'index.json'))
    print('Book:', index.get('bookTitle'))
    print('Total cards:', index.get('totalCards'))
    print('Last pushed ID:', progress.get('lastPushedId'))
    print('Last push date:', progress.get('lastPushDate'))
    succ = [h for h in progress.get('pushHistory', []) if h.get('status') == 'success']
    print('Successful pushes:', len(succ))
    print('History entries:', len(progress.get('pushHistory', [])))
    nxt = get_next_index(progress, index)
    if nxt is None:
        print('Status: ALL CARDS PUSHED [DONE]')
    else:
        print('Next card:', index['items'][nxt], '(#%d)' % (nxt + 1))

def cmd_next(args):
    bd = book_dir(args.book)
    if not os.path.isdir(bd):
        out({'skip': True, 'reason': 'book_not_found', 'book': args.book})
        sys.exit(1)
    if not args.force and not is_workday():
        out({'skip': True, 'reason': 'weekend', 'date': today_str()})
        return
    progress = load_json(os.path.join(bd, 'progress.json'))
    index = load_json(os.path.join(bd, 'index.json'))
    if not args.force and progress.get('lastPushDate') == today_str():
        out({'skip': True, 'reason': 'already_pushed_today', 'date': today_str()})
        return
    nxt = get_next_index(progress, index)
    if nxt is None:
        out({'skip': True, 'reason': 'all_done', 'date': today_str()})
        return
    filename = index['items'][nxt]
    card_id = extract_card_id(filename)
    if not card_id:
        out({'skip': True, 'reason': 'bad_index_entry', 'entry': filename})
        sys.exit(1)
    # guard against duplicate ids (cards would silently overwrite each other)
    try:
        items = load_json(os.path.join(bd, 'items.json'))
        check_unique_ids(items)
    except ValueError as e:
        out({'skip': True, 'reason': 'duplicate_ids', 'error': str(e)})
        sys.exit(1)
    # lock: block a second same-day run mid-flight or after delivery
    if not acquire_lock(bd, card_id):
        lock = load_json(os.path.join(bd, '.push_lock')) if os.path.exists(os.path.join(bd, '.push_lock')) else {}
        reason = 'already_pushed_today' if lock.get('done') else 'push_in_progress'
        out({'skip': True, 'reason': reason, 'cardId': lock.get('cardId', ''), 'date': today_str()})
        return
    try:
        payload = build_payload(bd, args.book, card_id, filename, nxt)
    except ValueError as e:
        release_lock(bd, card_id, done=False)
        out({'skip': True, 'reason': 'card_not_found', 'error': str(e)})
        sys.exit(1)
    out(payload)

def cmd_mark(args):
    bd = book_dir(args.book)
    progress = load_json(os.path.join(bd, 'progress.json'))
    if args.status == 'success':
        progress['lastPushedId'] = args.id
        progress['lastPushDate'] = today_str()
        progress.setdefault('pushHistory', []).append({'id': args.id, 'date': today_str(), 'status': 'success'})
        release_lock(bd, args.id, done=True)
    else:
        # failure: keep history for audit but do NOT touch lastPushedId/lastPushDate
        progress.setdefault('pushHistory', []).append({'id': args.id, 'date': today_str(), 'status': args.status})
        release_lock(bd, args.id, done=False)
    save_json(os.path.join(bd, 'progress.json'), progress)
    out({'ok': True, 'marked': args.id, 'status': args.status})

def cmd_weekday(args):
    sys.exit(0 if is_workday() else 1)

def cmd_list_books(args):
    if not os.path.isdir(BOOKS_DIR):
        print('No books set up yet.')
        return
    books = [d for d in os.listdir(BOOKS_DIR) if os.path.isdir(os.path.join(BOOKS_DIR, d))]
    if not books:
        print('No books set up yet.')
        return
    for slug in sorted(books):
        cfg_path = os.path.join(BOOKS_DIR, slug, 'config.json')
        title = slug
        if os.path.exists(cfg_path):
            title = load_json(cfg_path).get('bookTitle', slug)
        idx_path = os.path.join(BOOKS_DIR, slug, 'index.json')
        total = '?'
        if os.path.exists(idx_path):
            total = load_json(idx_path).get('totalCards', '?')
        prog_path = os.path.join(BOOKS_DIR, slug, 'progress.json')
        pushed = 0
        if os.path.exists(prog_path):
            p = load_json(prog_path)
            pushed = len([h for h in p.get('pushHistory', []) if h.get('status') == 'success'])
        print(f'  {slug} | {title} | {pushed}/{total} pushed')

def main():
    ap = argparse.ArgumentParser(description='Book-to-learn push progress manager')
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('status'); s.add_argument('--book', required=True)
    n = sub.add_parser('next'); n.add_argument('--book', required=True); n.add_argument('--force', action='store_true')
    m = sub.add_parser('mark'); m.add_argument('--book', required=True); m.add_argument('id'); m.add_argument('status', choices=['success', 'fail'])
    sub.add_parser('weekday')
    sub.add_parser('list-books')
    args = ap.parse_args()
    try:
        {'status': cmd_status, 'next': cmd_next, 'mark': cmd_mark, 'weekday': cmd_weekday, 'list-books': cmd_list_books}.get(args.cmd, lambda a: ap.print_help())(args)
    except json.JSONDecodeError as e:
        out({'skip': True, 'reason': 'json_error', 'error': str(e)})
        sys.exit(1)
    except FileNotFoundError as e:
        out({'skip': True, 'reason': 'file_missing', 'error': str(e)})
        sys.exit(1)

if __name__ == '__main__':
    main()
