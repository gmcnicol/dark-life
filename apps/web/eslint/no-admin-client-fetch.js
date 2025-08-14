const rule = {
  meta: {
    type: "problem",
    docs: {
      description: "disallow direct client fetches to NEXT_PUBLIC_API_BASE_URL/admin",
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
    function hasAdminLiteral(node) {
      return (
        node.type === "Literal" &&
        typeof node.value === "string" &&
        node.value.startsWith("/admin")
      );
    }
    return {
      CallExpression(node) {
        if (
          node.callee.type === "Identifier" &&
          node.callee.name === "fetch" &&
          node.arguments.length > 0
        ) {
          const arg = node.arguments[0];
          if (
            arg.type === "BinaryExpression" &&
            isEnvBase(arg.left) &&
            hasAdminLiteral(arg.right)
          ) {
            context.report({ node, messageId: "forbidden" });
          }
          if (arg.type === "TemplateLiteral") {
            const hasEnv = arg.expressions.some(isEnvBase);
            const hasAdmin = arg.quasis.some((q) => q.value.raw.startsWith("/admin"));
            if (hasEnv && hasAdmin) {
              context.report({ node, messageId: "forbidden" });
            }
          }
        }
      },
    };
  },
};

export default rule;
