import React from 'react';
/** A stale lazy chunk after a local update must not leave an empty window. */
export default class RecoveryBoundary extends React.Component<{children:React.ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true}}
  render(){if(!this.state.failed)return this.props.children;return <main className="recovery-screen" role="alert"><h1>Let’s reopen your workspace</h1><p>This view could not load. If Company HQ was updated, reload to open the current version.</p><p>Saved conversations and drafts stay in your app data.</p><button className="primary-button" onClick={()=>window.location.reload()}>Reload Company HQ</button></main>}
}
