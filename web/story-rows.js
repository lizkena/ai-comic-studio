// Match chapters to their actual script provenance; retain standalone author episodes.
export function storyRows(chapters, episodes) {
 const used = new Set();
 const rows = chapters.map((chapter, index) => {
  const episode = episodes.find(ep => ep.source_chapters?.includes(chapter.id) || ep.scenes?.some(sc => sc.source_chapters?.includes(chapter.id)));
  if (episode) used.add(episode.id);
  return {id:chapter.id, chapter, episode, title:chapter.title, number:index+1, kind:'chapter', summary:chapter.summary||''};
 });
 for (const [index, episode] of episodes.entries()) {
  if (!used.has(episode.id)) rows.push({id:episode.id, chapter:null, episode, title:episode.title, number:index+1, kind:'episode', summary:episode.scenes?.[0]?.goal||''});
 }
 return rows;
}
