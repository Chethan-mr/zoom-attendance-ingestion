/**
 * Script Properties required (Project Settings → Script properties):
 *
 * CACHE_URL
 *   Raw URL of data/manual_attendance_cache.json on GitHub, e.g.
 *   https://raw.githubusercontent.com/Chethan-mr/zoom-attendance-ingestion/main/data/manual_attendance_cache.json
 *
 * GITHUB_TOKEN
 *   Fine-grained PAT with:
 *   - Contents: Read (if private repo)
 *   - Contents: Read & Write (optional)
 *   - Actions / Administration: enough to create repository_dispatch
 *   Classic PAT scopes: repo + workflow
 *
 * GITHUB_REPO
 *   Chethan-mr/zoom-attendance-ingestion
 */

function getConfig_() {
  var props = PropertiesService.getScriptProperties();
  var cacheUrl = props.getProperty('CACHE_URL');
  var githubToken = props.getProperty('GITHUB_TOKEN');
  var githubRepo = props.getProperty('GITHUB_REPO') || 'Chethan-mr/zoom-attendance-ingestion';

  if (!cacheUrl) {
    throw new Error('Missing Script Property CACHE_URL');
  }
  if (!githubToken) {
    throw new Error('Missing Script Property GITHUB_TOKEN');
  }

  return {
    cacheUrl: cacheUrl,
    githubToken: githubToken,
    githubRepo: githubRepo
  };
}
