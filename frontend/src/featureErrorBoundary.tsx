import React from "react";

type Props = {
  children: React.ReactNode;
  onRetry: () => void | Promise<void>;
  resetKey: string;
};

type State = { failed: boolean };

export class FeatureErrorBoundary extends React.Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error) {
    console.error("Feature panel failed to render", error);
  }

  componentDidUpdate(previous: Props) {
    if (this.state.failed && previous.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
  }

  private retry = async () => {
    this.setState({ failed: false });
    await this.props.onRetry();
  };

  render() {
    if (this.state.failed) {
      return <article className="feature-recovery" role="alert">
        <p className="eyebrow">DISPLAY RECOVERY</p>
        <h3>Access Control could not be displayed</h3>
        <p>The portal caught an unexpected response before it could affect the rest of the page.</p>
        <button type="button" onClick={this.retry}>Retry access data</button>
      </article>;
    }

    return this.props.children;
  }
}
