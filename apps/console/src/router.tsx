// Route tree — docs/60-interface/console.md §2
import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";

import { RootLayout } from "./routes/__root";
import { ApprovalsPage } from "./routes/approvals";
import { ExplainPage } from "./routes/explain";
import { IncidentsPage } from "./routes/incidents";
import { LabPage } from "./routes/lab";
import { MemoryPage } from "./routes/memory";
import { PoliciesPage } from "./routes/policies";
import { PulsePage } from "./routes/pulse";
import { TimeMachinePage } from "./routes/timemachine";
import { WarRoomPage } from "./routes/war-room";
import { SlosPage } from "./routes/slos";

const rootRoute = createRootRoute({ component: RootLayout });

const routeTree = rootRoute.addChildren([
  createRoute({ getParentRoute: () => rootRoute, path: "/", component: PulsePage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/incidents", component: IncidentsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/incidents/$key", component: WarRoomPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/approvals", component: ApprovalsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/slos", component: SlosPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/memory", component: MemoryPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/timemachine/$key", component: TimeMachinePage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/policies", component: PoliciesPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/lab", component: LabPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/explain", component: ExplainPage }),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
