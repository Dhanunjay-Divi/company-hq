import { useEffect, useMemo, useRef, useState } from 'react';
import {
  GraphView,
  type GraphActivityItem,
  type GraphDataPort,
  type GraphDomainRef,
  type GraphEdge,
  type GraphEventPort,
  type GraphNode,
  type GraphNodePosition,
  type GraphParticle,
} from '@claude-teams/agent-graph';

export interface ClawTeamMember {
  name: string;
  memberKey?: string;
  inboxName?: string;
  agentId?: string;
  agentType?: string;
  inboxCount?: number;
}

export type ClawTaskStatus = 'pending' | 'in_progress' | 'completed' | 'blocked';

export interface ClawTeamTask {
  id: string;
  subject: string;
  description?: string;
  owner?: string;
  status?: ClawTaskStatus;
  blockedBy?: string[];
  blocked_by?: string[];
  blocks?: string[];
  updatedAt?: string;
  updated_at?: string;
}

export interface ClawTeamMessage {
  id?: string;
  requestId?: string;
  timestamp?: string;
  type?: string;
  from?: string;
  to?: string;
  fromKey?: string;
  toKey?: string;
  fromLabel?: string;
  toLabel?: string;
  content?: string;
}

export interface ClawTeamSnapshot {
  team: {
    name: string;
    description?: string;
    leaderName?: string;
    leadAgentId?: string;
  };
  members?: ClawTeamMember[];
  tasks?: Partial<Record<ClawTaskStatus, ClawTeamTask[]>>;
  messages?: ClawTeamMessage[];
}

export interface CompanyMemberProfile {
  displayName?: string;
  department?: string;
  model?: string;
  reportsTo?: string;
}

export interface CompanyProfile {
  members?: Record<string, CompanyMemberProfile>;
  projectLabel?: string;
  goal?: string;
}

export interface NativeRuntimeStatus {
  children?: {threadId:string;status?:string;stale?:boolean;model?:string}[];
  state?: 'offline' | 'starting' | 'idle' | 'running' | 'awaiting_approval' | 'stopping' | 'error' | string;
  model?: string;
  threadId?: string;
  connected?: boolean;
}

export interface TeamGraphProps {
  snapshot: ClawTeamSnapshot;
  company: CompanyProfile;
  runtime?: NativeRuntimeStatus;
  onSelectMember?: (memberName: string) => void;
  onSelectTask?: (taskId: string) => void;
  onMessageMember?: (memberName: string) => void;
  className?: string;
}

const MEMBER_PREFIX = 'member:';
const TASK_PREFIX = 'task:';
const MESSAGE_EFFECT_WINDOW_MS = 8_000;
const palette = ['#4de4d0', '#74a7ff', '#b793ff', '#ffb86b', '#6ed89d', '#f28aa5'];

function bare(value: string | undefined): string {
  return (value ?? '').replace(/^local_/, '');
}

function stableColor(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

function parseTime(value: string | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function allTasks(snapshot: ClawTeamSnapshot): Array<ClawTeamTask & { status: ClawTaskStatus }> {
  const result: Array<ClawTeamTask & { status: ClawTaskStatus }> = [];
  for (const status of ['pending', 'in_progress', 'completed', 'blocked'] as const) {
    for (const task of snapshot.tasks?.[status] ?? []) result.push({ ...task, status });
  }
  return result;
}

interface MemberRecord {
  key: string;
  member: ClawTeamMember;
  profile: CompanyMemberProfile;
  aliases: Set<string>;
}

function memberRecords(snapshot: ClawTeamSnapshot, company: CompanyProfile): MemberRecord[] {
  const profiles = company.members ?? {};
  const members = snapshot.members ?? [];
  return members.map((member) => {
    const aliases = new Set(
      [member.name, member.memberKey, member.inboxName, bare(member.name), bare(member.memberKey), bare(member.inboxName)].filter(
        (value): value is string => Boolean(value)
      )
    );
    const profileEntry = Object.entries(profiles).find(([key, profile]) =>
      aliases.has(key) || aliases.has(bare(key)) || profile.displayName === member.name
    );
    const key = profileEntry?.[0] ?? bare(member.name);
    aliases.add(key);
    aliases.add(bare(key));
    return { key, member, profile: profileEntry?.[1] ?? {}, aliases };
  });
}

function endpointRecord(records: MemberRecord[], ...values: Array<string | undefined>): MemberRecord | undefined {
  return records.find((record) => values.some((value) => value && (record.aliases.has(value) || record.aliases.has(bare(value)))));
}

function messageId(message: ClawTeamMessage, index: number): string {
  return message.requestId ?? message.id ?? `${message.timestamp ?? 'unknown'}-${index}`;
}

function activityFor(record: MemberRecord, messages: ClawTeamMessage[], records: MemberRecord[]): GraphActivityItem[] {
  return messages
    .map((message, index) => ({ message, index }))
    .filter(({ message }) => {
      const source = endpointRecord(records, message.fromKey, message.from);
      const target = endpointRecord(records, message.toKey, message.to);
      return source?.key === record.key || target?.key === record.key;
    })
    .sort((left, right) => parseTime(right.message.timestamp) - parseTime(left.message.timestamp))
    .slice(0, 4)
    .map(({ message, index }) => {
      const source = endpointRecord(records, message.fromKey, message.from);
      const target = endpointRecord(records, message.toKey, message.to);
      const incoming = target?.key === record.key;
      const counterpart = incoming
        ? source?.profile.displayName ?? message.fromLabel ?? message.from ?? 'User'
        : target?.profile.displayName ?? message.toLabel ?? message.to ?? 'Team';
      return {
        id: `activity:${messageId(message, index)}:${record.key}`,
        kind: 'inbox_message',
        timestamp: message.timestamp ?? '',
        title: `${incoming ? 'From' : 'To'} ${counterpart}`,
        preview: message.content ?? '',
        authorLabel: incoming ? counterpart : record.profile.displayName ?? record.member.name,
      };
    });
}

function graphTaskStatus(status: ClawTaskStatus): NonNullable<GraphNode['taskStatus']> {
  if (status === 'blocked') return 'pending';
  return status;
}

function taskNodeState(status: ClawTaskStatus): GraphNode['state'] {
  if (status === 'completed') return 'complete';
  if (status === 'in_progress') return 'active';
  return 'waiting';
}

function leadRuntimePresentation(runtime: NativeRuntimeStatus | undefined): Pick<
  GraphNode,
  'state' | 'runtimeLabel' | 'launchVisualState' | 'launchStatusLabel' | 'pendingApproval'
> | null {
  if (!runtime?.state) return null;
  const labels: Record<string, string> = {
    offline: 'Native runtime not started',
    starting: 'Native runtime starting',
    idle: 'Native runtime ready',
    running: 'Native runtime working',
    awaiting_approval: 'Native runtime needs approval',
    stopping: 'Native runtime stopping',
    error: 'Native runtime needs attention',
  };
  const states: Record<string, GraphNode['state']> = {
    offline: 'idle',
    starting: 'active',
    idle: 'idle',
    running: 'active',
    awaiting_approval: 'waiting',
    stopping: 'waiting',
    error: 'error',
  };
  const launchStates: Partial<Record<string, GraphNode['launchVisualState']>> = {
    starting: 'runtime_pending',
    awaiting_approval: 'permission_pending',
    stopping: 'settling',
    error: 'error',
  };
  return {
    state: states[runtime.state] ?? 'idle',
    runtimeLabel: [runtime.model, labels[runtime.state] ?? `Native runtime: ${runtime.state}`].filter(Boolean).join(' · '),
    launchVisualState: launchStates[runtime.state],
    launchStatusLabel: labels[runtime.state] ?? `Native runtime: ${runtime.state}`,
    pendingApproval: runtime.state === 'awaiting_approval',
  };
}

function hierarchyDepth(record: MemberRecord, byKey: Map<string, MemberRecord>): number {
  const visited = new Set<string>();
  let depth = 0;
  let cursor: MemberRecord | undefined = record;
  while (cursor?.profile.reportsTo && byKey.has(cursor.profile.reportsTo) && !visited.has(cursor.key)) {
    visited.add(cursor.key);
    cursor = byKey.get(cursor.profile.reportsTo);
    depth += 1;
  }
  return depth;
}

function buildPositions(records: MemberRecord[], tasks: Array<ClawTeamTask & { status: ClawTaskStatus }>): Record<string, GraphNodePosition> {
  const byKey = new Map(records.map((record) => [record.key, record]));
  const levels = new Map<number, MemberRecord[]>();
  for (const record of records) {
    const depth = hierarchyDepth(record, byKey);
    levels.set(depth, [...(levels.get(depth) ?? []), record]);
  }
  const positions: Record<string, GraphNodePosition> = {};
  for (const depth of [...levels.keys()].sort((left, right) => left - right)) {
    const level = levels.get(depth) ?? [];
    const width = Math.max(1, level.length - 1) * 235;
    level.forEach((record, index) => {
      const parentPosition = record.profile.reportsTo
        ? positions[`${MEMBER_PREFIX}${record.profile.reportsTo}`]
        : undefined;
      const x = depth > 1 && parentPosition && level.length === 1
        ? parentPosition.x
        : index * 235 - width / 2;
      positions[`${MEMBER_PREFIX}${record.key}`] = { x, y: depth * 160 };
    });
  }
  const tasksByOwner = new Map<string, Array<ClawTeamTask & { status: ClawTaskStatus }>>();
  for (const task of tasks) {
    const owner = endpointRecord(records, task.owner);
    if (!owner) continue;
    tasksByOwner.set(owner.key, [...(tasksByOwner.get(owner.key) ?? []), task]);
  }
  for (const [ownerKey, ownerTasks] of tasksByOwner) {
    const ownerPosition = positions[`${MEMBER_PREFIX}${ownerKey}`];
    if (!ownerPosition) continue;
    ownerTasks.forEach((task, index) => {
      positions[`${TASK_PREFIX}${task.id}`] = {
        x: ownerPosition.x + (ownerTasks.length === 1 ? 0 : index % 2 === 0 ? -92 : 92),
        y: ownerPosition.y + 88 + Math.floor(index / 2) * 58,
      };
    });
  }
  return positions;
}

export function adaptClawTeamGraph(
  snapshot: ClawTeamSnapshot,
  company: CompanyProfile,
  particleMessages: ClawTeamMessage[] = [],
  runtime?: NativeRuntimeStatus
): GraphDataPort {
  const records = memberRecords(snapshot, company);
  const byKey = new Map(records.map((record) => [record.key, record]));
  const tasks = allTasks(snapshot);
  // Completed work remains available in the Tasks view. The upstream renderer's
  // showCompletedTasks option is not applied to fit bounds, so including history
  // here shrinks a small active team until its people are unreadable.
  const graphTasks = tasks.filter((task) => task.status !== 'completed');
  const messages = snapshot.messages ?? [];
  const leadName = snapshot.team.leaderName;
  const lead = endpointRecord(records, leadName) ?? records.find((record) => !record.profile.reportsTo);
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  for (const record of records) {
    const currentTask = tasks.find((task) => task.status === 'in_progress' && record.aliases.has(task.owner ?? ''));
    const depth = hierarchyDepth(record, byKey);
    const isLead = record.key === lead?.key;
    const child=runtime?.children?.find(worker=>worker.threadId===record.member.agentId);
    const childState=child?.status==='active'?'running':child?.status==='pendingInit'?'starting':child?.status==='systemError'?'error':child?.status;
    const liveLead = isLead ? leadRuntimePresentation(runtime) : child&&!child.stale ? leadRuntimePresentation({state:childState,model:child.model}) : null;
    nodes.push({
      id: `${MEMBER_PREFIX}${record.key}`,
      kind: isLead ? 'lead' : 'member',
      label: record.profile.displayName ?? record.member.name,
      avatarUrl: `/assets/avatars/${String(record.key === lead?.key ? 1 : ([...(record.profile.displayName ?? record.member.name)].reduce((n,c)=>n+c.charCodeAt(0),0)%6)+1).padStart(2,'0')}.png`,
      state: liveLead?.state ?? 'idle',
      color: stableColor(record.profile.department ?? record.key),
      // Full department is shown in the inspector; keep graph labels legible.
      role: undefined,
      runtimeLabel: liveLead?.runtimeLabel ?? (record.profile.model || 'Model not recorded'),
      launchVisualState: liveLead ? liveLead.launchVisualState : 'registered_only',
      launchStatusLabel: liveLead?.launchStatusLabel ?? 'Recorded · runtime unknown',
      pendingApproval: liveLead?.pendingApproval,
      currentTaskId: currentTask?.id ?? null,
      currentTaskSubject: currentTask?.subject,
      activityItems: activityFor(record, messages, records),
      activityOverflowCount: Math.max(0, messages.filter((message) => {
        const source = endpointRecord(records, message.fromKey, message.from);
        const target = endpointRecord(records, message.toKey, message.to);
        return source?.key === record.key || target?.key === record.key;
      }).length - 4),
      semanticSummary: `${record.profile.department ?? 'Team'} · ${record.member.inboxCount ?? 0} inbox`,
      hierarchyDepth: depth,
      domainRef: { kind: 'member', teamName: snapshot.team.name, memberName: record.key },
    });
    const parentKey = record.profile.reportsTo;
    if (parentKey && byKey.has(parentKey)) {
      edges.push({
        id: `reports:${parentKey}:${record.key}`,
        source: `${MEMBER_PREFIX}${parentKey}`,
        target: `${MEMBER_PREFIX}${record.key}`,
        type: 'parent-child',
        label: 'reports to',
        alwaysVisible: true,
        routing: 'orthogonal',
      });
    }
  }

  const taskById = new Map(graphTasks.map((task) => [task.id, task]));
  for (const task of graphTasks) {
    const owner = endpointRecord(records, task.owner);
    const blockedBy = task.blockedBy ?? task.blocked_by ?? [];
    nodes.push({
      id: `${TASK_PREFIX}${task.id}`,
      kind: 'task',
      label: task.subject,
      sublabel: task.subject,
      displayId: `#${task.id.slice(0, 8)}`,
      state: taskNodeState(task.status),
      color: task.status === 'blocked' ? '#ff8a86' : undefined,
      ownerId: owner ? `${MEMBER_PREFIX}${owner.key}` : null,
      taskStatus: graphTaskStatus(task.status),
      isBlocked: task.status === 'blocked' || blockedBy.length > 0,
      blockedByDisplayIds: blockedBy.map((id) => `#${id.slice(0, 8)}`),
      blocksDisplayIds: (task.blocks ?? []).map((id) => `#${id.slice(0, 8)}`),
      taskZoomVisibility: 'overview',
      taskOverviewStyle: 'card',
      domainRef: { kind: 'task', teamName: snapshot.team.name, taskId: task.id },
    });
    if (owner) {
      edges.push({
        id: `owns:${owner.key}:${task.id}`,
        source: `${MEMBER_PREFIX}${owner.key}`,
        target: `${TASK_PREFIX}${task.id}`,
        type: 'ownership',
      });
    }
    for (const blockerId of blockedBy) {
      if (!taskById.has(blockerId)) continue;
      edges.push({
        id: `blocks:${blockerId}:${task.id}`,
        source: `${TASK_PREFIX}${blockerId}`,
        target: `${TASK_PREFIX}${task.id}`,
        type: 'blocking',
        alwaysVisible: true,
      });
    }
  }

  const messageEdges = new Map<string, GraphEdge>();
  messages.forEach((message, index) => {
    const source = endpointRecord(records, message.fromKey, message.from);
    const target = endpointRecord(records, message.toKey, message.to);
    if (!source || !target || source.key === target.key) return;
    const id = `message:${source.key}:${target.key}`;
    const previous = messageEdges.get(id);
    messageEdges.set(id, {
      id,
      source: `${MEMBER_PREFIX}${source.key}`,
      target: `${MEMBER_PREFIX}${target.key}`,
      type: 'message',
      label: message.content || 'Inbox message',
      aggregateCount: (previous?.aggregateCount ?? 0) + 1,
    });
  });
  edges.push(...messageEdges.values());

  const particles: GraphParticle[] = [];
  particleMessages.forEach((message, index) => {
    const source = endpointRecord(records, message.fromKey, message.from);
    const target = endpointRecord(records, message.toKey, message.to);
    if (!source || !target || source.key === target.key) return;
    const edgeId = `message:${source.key}:${target.key}`;
    particles.push({
      id: `particle:${messageId(message, index)}`,
      edgeId,
      progress: 0,
      kind: 'inbox_message',
      color: '#56e5d2',
      label: 'message',
      preview: message.content ?? '',
    });
  });

  return {
    nodes,
    edges,
    particles,
    teamName: company.projectLabel ?? snapshot.team.name,
    teamColor: '#4de4d0',
    layout: {
      version: 'stable-slots-v1',
      mode: 'hierarchical',
      showActivity: true,
      showLogs: false,
      showTasks: true,
      fitTaskRowsToContent: true,
      ownerOrder: records.map((record) => `${MEMBER_PREFIX}${record.key}`),
      slotAssignments: {},
      nodePositions: buildPositions(records, graphTasks),
    },
  };
}

function useNewMessageEffects(messages: ClawTeamMessage[]): ClawTeamMessage[] {
  const seen = useRef(new Set<string>());
  const [active, setActive] = useState<ClawTeamMessage[]>([]);
  useEffect(() => {
    const now = Date.now();
    const fresh = messages.filter((message, index) => {
      const id = messageId(message, index);
      if (seen.current.has(id)) return false;
      const age = now - parseTime(message.timestamp);
      if (age < 0 || age > MESSAGE_EFFECT_WINDOW_MS) return false;
      seen.current.add(id);
      return true;
    });
    if (!fresh.length) return;
    setActive(fresh);
    const timeout = window.setTimeout(() => setActive([]), 2_400);
    return () => window.clearTimeout(timeout);
  }, [messages]);
  return active;
}

export default function TeamGraph({
  snapshot,
  company,
  runtime,
  onSelectMember,
  onSelectTask,
  onMessageMember,
  className,
}: TeamGraphProps): React.JSX.Element {
  const activeMessages = useNewMessageEffects(snapshot.messages ?? []);
  const [revealNodeRequest, setRevealNodeRequest] = useState<{ nodeId: string; requestId: number } | null>(null);
  const data = useMemo(
    () => adaptClawTeamGraph(snapshot, company, activeMessages, runtime),
    [activeMessages, company, runtime, snapshot]
  );
  const events = useMemo<GraphEventPort>(() => {
    const select = (ref: GraphDomainRef): void => {
      if (ref.kind === 'member' || ref.kind === 'lead') {
        setRevealNodeRequest((previous) => ({
          nodeId: `${MEMBER_PREFIX}${ref.memberName}`,
          requestId: (previous?.requestId ?? 0) + 1,
        }));
        onSelectMember?.(ref.memberName);
      }
      if (ref.kind === 'task') {
        setRevealNodeRequest((previous) => ({
          nodeId: `${TASK_PREFIX}${ref.taskId}`,
          requestId: (previous?.requestId ?? 0) + 1,
        }));
        onSelectTask?.(ref.taskId);
      }
    };
    return {
      onNodeClick: select,
      onNodeDoubleClick: select,
      onOpenMemberProfile: (memberName) => onSelectMember?.(memberName),
      onOpenTaskDetail: (taskId) => onSelectTask?.(taskId),
      onSendMessage: (memberName) => onMessageMember?.(memberName),
    };
  }, [onMessageMember, onSelectMember, onSelectTask]);

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%', minHeight: 0 }}>
      <GraphView
        data={data}
        events={events}
        className="company-hq-agent-graph"
        isSurfaceActive
        showMinimap={data.nodes.length > 8}
        minimapLabel="Team map"
        layoutModeCycle={['hierarchical']}
        revealNodeRequest={revealNodeRequest}
        config={{
          backgroundColor: '#080a13',
          showHexGrid: false,
          showDotGrid: true,
          showStarField: true,
          showSpaceEffects: false,
          bloomIntensity: 0.55,
          showActivity: true,
          showLogs: false,
          showProcesses: false,
          showTasks: true,
          showEdges: true,
          showEdgeLabels: false,
          animationEnabled: true,
          particleSpeed: 1,
          nodeStateColors: { idle: '#4de4d0' },
          taskStatusColors: {
            pending: '#f3bf61',
            in_progress: '#68a8ff',
            completed: '#65d49a',
          },
        }}
      />
    </div>
  );
}
