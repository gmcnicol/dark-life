const rule = {
  meta: {
    type: "problem",
    docs: {
      description: "disallow direct client fetches to admin endpoints",
    },
    messages: {
      forbidden: "Use /api/admin route handlers instead of fetching NEXT_PUBLIC_API_BASE_URL/admin",
    },
  },
  create(context) {
    function isEnvBase(node) {
      return (
        node.type === "MemberExpression" &&
        node.object.type === "MemberExpression" &&
        node.object.object.type === "Identifier" &&
        node.object.object.name === "process" &&
        node.object.property.type === "Identifier" &&
        node.object.property.name === "env" &&
        node.property.type === "Identifier" &&
        node.property.name === "NEXT_PUBLIC_API_BASE_URL"
      );
    }

    function literalHasAdmin(node) {
      return (
        node.type === "Literal" &&
        typeof node.value === "string" &&
        node.value.includes("/admin") &&
        !node.value.startsWith("/api/admin")
      );
    }

    function templateValue(node) {
      return node.quasis.map((q) => q.value.raw).join("");
    }

    return {
      CallExpression(node) {
        if (
          node.callee.type === "Identifier" &&
          node.callee.name === "fetch" &&
          node.arguments.length > 0
        ) {
          const arg = node.arguments[0];

          if (literalHasAdmin(arg)) {
            context.report({ node, messageId: "forbidden" });
            return;
          }

          if (
            arg.type === "BinaryExpression" &&
            isEnvBase(arg.left) &&
            literalHasAdmin(arg.right)
          ) {
            context.report({ node, messageId: "forbidden" });
            return;
          }

          if (arg.type === "TemplateLiteral") {
            const value = templateValue(arg);
            const hasEnv = arg.expressions.some(isEnvBase);
            const hasAdmin = value.includes("/admin");
            const allowed = value.startsWith("/api/admin");
            if ((hasEnv && hasAdmin) || (!hasEnv && hasAdmin && !allowed)) {
              context.report({ node, messageId: "forbidden" });
            }
          }
        }
      },
    };
  },
};

export default rule;
