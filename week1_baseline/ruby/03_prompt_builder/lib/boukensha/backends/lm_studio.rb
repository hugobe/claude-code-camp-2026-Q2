require_relative "base"

module Boukensha
  module Backends
    class LmStudio < Base
      MODELS = {
        "google/gemma-4-12b-qat" => {
          context_window: 256_000,
          cost_per_million: { input: 0.0, output: 0.0 },
          usage_unit: :local_compute
        }
      }.freeze

      def initialize(host: "http://localhost:1234/v1", model:)
        @host = host
        configure_model(model)
      end

      def to_messages(system, messages)
        system_message = [{ role: "system", content: system }]
        conversation   = messages.map do |msg|
          case msg.role
          when :tool_result
            { role: "tool", tool_call_id: msg.tool_use_id, content: msg.content }
          else
            { role: msg.role.to_s, content: msg.content }
          end
        end
        system_message + conversation
      end

      def to_tools(tools)
        tools.values.map do |tool|
          {
            type: "function",
            function: {
              name: tool.name,
              description: tool.description,
              parameters: {
                type: "object",
                properties: tool.parameters,
                required: tool.parameters.keys.map(&:to_s)
              }
            }
          }
        end
      end

      def to_payload(context, max_output_tokens: 1024)
        {
          model: @model,
          stream: false,
          messages: to_messages(context.system, context.messages),
          tools: to_tools(context.tools),
          max_tokens: max_output_tokens
        }
      end

      def headers
        { "Content-Type" => "application/json" }
      end

      def url
        "#{@host}/chat/completions"
      end
    end
  end
end
