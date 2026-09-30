# Demo script (5–7 minutes)

Before the demo: API and web app running (see README), logged in as the reviewer in a second tab,
and every demo question asked once so its AI responses are cached (`data/llm_cache/`), which lets
the demo run even if the network or the Gemini API fails.

1. **Zero data entry.** Open DSpace
   (http://14.139.119.23:8080/dspace/handle/123456789/326, Ninth Expedition report). Then open
   `/expeditions/ISEA-9` in our app: the same report and its papers, grouped by NCPOR's own
   sections, linked to the expedition, harvested with no manual entry. Point at the
   "Confirmed by NCPOR catalogue" and "Machine-linked (unconfirmed)" labels.
2. **Cited answer.** Staff console → *Draft new content* → *Cited answer*:
   "Has India measured how the Dakshin Gangotri glacier is moving?" The draft opens in review:
   every sentence green/amber/red with its source. Click *Show sources* → *open page*: the
   scan of the iceberg/glacier paper beside its text (printed pp. 239–250).
3. **Refusal.** Same form: "How fast do Mars rovers drive?" → "No NCPOR source found for this",
   with the reason. On the public *Ask* page the same question is refused too.
4. **Lesson.** *Lesson unit*: search "glacier snout monitoring", tick 2–3 passages, topic
   "Glaciers and how they move", Class 11 → draft. Show a red sentence, edit or delete it, approve
   (your name is recorded), publish, then *Draft Hindi version* → approve → publish. Open
   `/learn`: English and Hindi, source list, reviewer name.
5. **Announcement.** *Expedition announcement* for ISEA-9 → web post and three social posts,
   each sentence cited → approve → publish. It appears on `/expeditions/ISEA-9`.
6. **Coverage.** `/coverage`: reports 6–8 listed but not published; expeditions 31–46 known from
   NCPOR news but with no report in DSpace; no dataset links until NPDC access is granted.
7. **Accuracy.** `/evaluation`: the two scores from the verified test set, with failures listed.
   Report whatever they are.

Audit trail for any of the above: staff console → *Audit log*.
