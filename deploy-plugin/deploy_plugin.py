import os
from datetime import datetime

import git
from airflow import conf
from airflow.plugins_manager import AirflowPlugin
from airflow.www_rbac.decorators import action_logging
from flask import render_template, flash, redirect, request
from flask_appbuilder import BaseView, has_access, expose
from flask_wtf import FlaskForm
from git.cmd import GitCommandError
from wtforms.fields import SelectField


class DeploymentView(BaseView):
    plugins_folder = conf.get("core", "plugins_folder")
    template_folder = os.path.join(plugins_folder, "deploy-plugin")
    repo = git.Repo(conf.get("core", "dags_folder"))
    route_base = "/deployment"

    def render(self, template, **context):
        return render_template(
            template,
            base_template=self.appbuilder.base_template,
            appbuilder=self.appbuilder,
            **context,
        )

    @expose("/status")
    @has_access
    @action_logging
    def list(self):
        title = "Deployment"
        data = dict()
        remotes = list()

        for rem in self.repo.remotes:
            remotes.append((rem.name, rem.url))
            try:
                rem.fetch(prune=True)
            except GitCommandError as gexc:
                flash(str(gexc), "error")

        data["remotes"] = remotes
        data["active_branch"] = self.repo.active_branch.name
        data["sha"] = self.repo.head.object.hexsha
        data["commit_message"] = self.repo.head.object.message
        data["author"] = self.repo.head.object.author
        data["committed_date"] = datetime.fromtimestamp(
            self.repo.head.object.committed_date
        ).strftime("%Y-%m-%d %H:%M:%S")
        data["local_branches"] = [brn.name for brn in self.repo.branches]
        remote_branches = [
            ref.name for ref in self.repo.remotes.origin.refs if "HEAD" not in ref.name
        ]

        form = GitBranchForm()
        form.git_branches.choices = [(brn, brn) for brn in remote_branches]
        form.git_branches.default = "origin/master"

        return self.render_template("deploy.html", title=title, form=form, data=data)

    @expose("/deploy", methods=["POST"])
    @has_access
    @action_logging
    def deploy(self):

        new_branch = request.form.get("git_branches")
        new_local_branch = new_branch.replace("origin/", "")

        try:
            self.repo.git.checkout(new_local_branch)
            self.repo.git.pull()
            if new_local_branch == self.repo.active_branch.name:
                flash(f"Successfully updated branch: {new_local_branch}")
            else:
                flash(f"Successfully changed to branch: {new_local_branch}")
        except GitCommandError as gexc:
            flash(str(gexc), "error")
        return redirect("/deployment/status")


v_appbuilder_view = DeploymentView()
v_appbuilder_package = {
    "name": "Deployment",
    "category": "Admin",
    "view": v_appbuilder_view,
}


class AirflowDeploymentPlugin(AirflowPlugin):
    name = "deploy_plugin"
    appbuilder_views = [v_appbuilder_package]


class GitBranchForm(FlaskForm):
    git_branches = SelectField("Git branch")
