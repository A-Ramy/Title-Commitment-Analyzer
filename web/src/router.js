// Hash routes: #/  #/deal/12  #/analyze  #/training  #/knowledge  #/team  #/settings
import { useEffect, useState } from 'preact/hooks';

const read = () => (location.hash.replace(/^#\/?/, '') || 'deals').split('/');

export function useRoute() {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => { setRoute(read()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

export const go = path => { location.hash = '#/' + path; };
