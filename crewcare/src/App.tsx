import { useState } from 'react'

import type { Role } from './auth/roles'
import { DemoBanner } from './components/DemoBanner'
import { PhoneFrame } from './components/PhoneFrame'
import { Dashboard } from './screens/admin/Dashboard'
import { SignIn } from './screens/SignIn'
import { ChannelSelect } from './screens/worker/ChannelSelect'
import { MessageThread } from './screens/worker/MessageThread'
import { channels, type Channel } from './theme'

/**
 * Routing on the resolved role.
 *
 * The role arrives already resolved from auth/roles.ts; nothing downstream
 * asks the person which one they are, and the two paths never meet. Signing
 * out bumps `session`, which remounts the whole subtree — the surest way to
 * guarantee no answer, image or draft survives a reset.
 *
 * The employee id is held here for the worker's session because linking a
 * phone needs it. It is never written to storage and never reaches the admin
 * subtree, which takes no props at all beyond a sign-out callback.
 */
type Route =
  | { screen: 'signin' }
  | { screen: 'worker'; employeeId: string; channel: Channel | null }
  | { screen: 'admin' }

export function App() {
  const [route, setRoute] = useState<Route>({ screen: 'signin' })
  const [session, setSession] = useState(0)

  function signIn(role: Role, employeeId: string) {
    setRoute(
      role === 'admin'
        ? { screen: 'admin' }
        : { screen: 'worker', employeeId, channel: null },
    )
  }

  function signOut() {
    setRoute({ screen: 'signin' })
    setSession((n) => n + 1)
  }

  switch (route.screen) {
    case 'signin':
      return <SignIn key={session} onContinue={signIn} />

    case 'admin':
      return <Dashboard key={session} onSignOut={signOut} />

    case 'worker':
      return route.channel ? (
        <ThreadPage key={session} channel={route.channel} onSignOut={signOut} />
      ) : (
        <ChannelSelect
          key={session}
          employeeId={route.employeeId}
          onChoose={(channel) =>
            setRoute({ screen: 'worker', employeeId: route.employeeId, channel })
          }
          onSignOut={signOut}
        />
      )
  }
}

function ThreadPage({ channel, onSignOut }: { channel: Channel; onSignOut: () => void }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="simulated thread. No message is sent and no answer leaves this tab." />
      </div>
      <PhoneFrame statusBarFg={channels[channel].headerFg}>
        <MessageThread channel={channel} onSignOut={onSignOut} />
      </PhoneFrame>
    </div>
  )
}
