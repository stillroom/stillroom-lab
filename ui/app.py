"""Read-only local UI. Provisioning/ingestion/artifact generation stay operator-only."""
from datetime import date
import os

import psycopg
import streamlit as st

from agent.provider import ProviderError, provider_from_env
from agent.runner import Agent, AgentError
from services.downloads import read_artifact
from services.query import PermissionContext, QueryService


def main() -> None:
    st.set_page_config(page_title='Stillroom Lab', layout='wide')
    st.title('Stillroom Lab — evidence before answers')
    permission = PermissionContext(role=os.getenv('STILLROOM_ROLE', 'analyst'),
                                   client_id=os.getenv('STILLROOM_CLIENT_ID', 'CLIENT-1'))
    st.caption(f'Local prototype · {permission.role} / {permission.client_id} · '
               'No source or canonical writes. Governed queries append audit records. '
               'Artifact generation is not available in this UI.')
    st.caption('Inference is disabled by default. Explicit cloud opt-in sends your question '
               'and permission context to the selected provider, never retrieved source records.')
    question = st.text_area('Question', key='question', max_chars=16000)
    as_of = st.date_input('As of', value=date(2026, 9, 1), key='as_of')
    use_period = st.checkbox('Cash receipts: restrict period start', key='use_period')
    start = st.date_input('Period start', value=date(2026, 8, 1), key='period_start') if use_period else None
    if st.button('Ask governed agent', key='ask'):
        st.session_state.pop('answer', None)
        try:
            provider = provider_from_env()  # fail closed before constructing a query service
            try:
                agent = Agent(QueryService(os.getenv('STILLROOM_SCHEMA', 'stillroom_v02')), provider)
                st.session_state['answer'] = agent.answer(question, permission, as_of=as_of, period_start=start)
            finally:
                provider.client.close()
        except (ProviderError, AgentError) as exc:
            st.error(str(exc))
        except (psycopg.Error, OSError, ValueError):
            st.error('Local query unavailable. An operator must provision and ingest the lab first.')
    answer = st.session_state.get('answer')
    if answer is not None:
        # Literal display: source strings cannot become active links/HTML/instructions.
        st.code(answer.text, language=None, wrap_lines=True)
        with st.expander('Proof manifest — all fields'):
            st.json(answer.manifest.model_dump(mode='json'))
    name = st.text_input('Existing artifact basename (output-workspace only)', key='artifact_name')
    if st.button('Load existing artifact', key='load_artifact'):
        st.session_state.pop('download', None)
        try:
            st.session_state['download'] = (name, read_artifact(name, permission))
        except (OSError, ValueError):
            st.error('Artifact unavailable, invalid, or outside your permission context.')
    download = st.session_state.get('download')
    if download is not None:
        st.download_button('Download verified artifact', data=download[1], file_name=download[0],
                           mime='application/octet-stream', on_click='ignore')


if __name__ == '__main__':
    main()
